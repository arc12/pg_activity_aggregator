from pg_shared import AnalyticsCore
import logging
from datetime import datetime as dt
import pandas as pd

# Aggregate count (and unique session ids) broken down by "tag", "plaything_name", "plaything_part", "specification_id", and storing to "agg-container" (see core_config.json)
# Aggregates are for one hour and one day, and date/times are UTC (Cosmos DB is not localised). i.e. the date roll-over is UTC. 
# TODO add a time zone so that the aggregated dates/times are Localised. i.e. assume that someone who wants a specific time zone will host a separate playground 

# This is meant to be called hourly and will fill up "max_agg_hours" (set in core_config.json) of missing entries.
# If there are no raw records for an hour, then an aggregate record with "tag", "plaything_name", "plaything_part", and "specification_id" all set to "-" and counts of 0 is saved.
# Otherwise, aggregate records for that hour are only created for those "tag", "plaything_name", "plaything_part", or "specification_id" with at least 1 raw record.
# Date records are created whenever an "dateT23" is computed.

def aggregator():
    ac = AnalyticsCore("basic-agg")

    if ac.record_activity_container is None or ac.aggregated_container is None:
        logging.info("Aborting aggregator(); activity aggregation is disabled.")
    else:
        # find the latest date_hr for agg data and compute the timestamp
        max_agg_dh = ac.aggregated_container.query_items("SELECT VALUE MAX(c.date_hr) FROM c", enable_cross_partition_query=True).next()
        if max_agg_dh is None:
            # catch case for new container for agg data; find the earliest date_hr in the raw activity log container
            first_ts = ac.record_activity_container.query_items("SELECT VALUE MIN(c._ts) FROM c", enable_cross_partition_query=True).next()
            start_ts = 3600 * (first_ts // 3600)  # timestamp for start of the first date-hour to aggregate for
        else:
            start_ts = 3600 + int(dt.strptime(max_agg_dh, "%Y-%m-%dT%H").timestamp())  # timestamp for start of the first date-hour to aggregate for

        # if the agg data is up to date, exit. This adds a small "safety margin"
        now_ts = dt.now().timestamp()
        if start_ts + 3600 + 60 >= now_ts:
            logging.info("Aborting aggregator(); aggregated data is up to date.")
            return
        
        # aggregate missing hour chunks, up to the max configured number of missing hours for one call to aggregator()
        n_updates = 0
        while (start_ts + 3600 < now_ts) and (n_updates < ac.activity_config.get("max_agg_hours", 24)):
            end_ts = start_ts + 3600
            # get raw
            qry = "SELECT c.tag, c.plaything_name, c.plaything_part, c.specification_id, c.session_id,"\
                  "SUBSTRING(TimestampToDateTime(c._ts * 1000), 0, 13) as date_hr FROM c "\
                  f"WHERE c._ts >= {start_ts} AND c._ts < {end_ts}"
            items = ac.record_activity_container.query_items(qry, enable_cross_partition_query=True)
            df = pd.DataFrame(items).fillna("-")
            if len(df) == 0:
                # create a nil activity record
                dh = dt.fromtimestamp(start_ts).strftime("%Y-%m-%dT%H")
                rec = {"tag": "-", "plaything_name": "-", "plaything_part": "-", "specification_id": "-", "date_hr": dh, "count": 0, "sessions": 0, "start_ts": start_ts, "partition_key": "1"}
                ac.aggregated_container.create_item(rec, enable_automatic_id_generation=True)
            else:
                # compute and store aggregated                
                # there is no bulk API to CosmosDB (for Python SDK), so loop. NB there is actually an async client but I don't think it is warranted here
                for ix, group in df.groupby(by=["tag", "plaything_name", "plaything_part", "specification_id"]):
                    rec = group.iloc[0].drop(["session_id"]).to_dict()
                    rec.update({"count": len(group), "sessions": group.session_id.nunique(), "start_ts": start_ts, "partition_key": "1"})  # force single partition
                    ac.aggregated_container.create_item(rec, enable_automatic_id_generation=True)

            # check for last hour and make a date record, re-querying the agg container
            if rec["date_hr"].endswith("T23"):
                d = rec["date_hr"][:10]
                d_start_ts = start_ts - 23 * 3600
                qry = f"SELECT c.tag, c.plaything_name, c.plaything_part, c.specification_id, c.count, c.sessions FROM c WHERE STARTSWITH(c.date_hr, '{d}')"
                hours_df = pd.DataFrame(ac.aggregated_container.query_items(qry, enable_cross_partition_query=True))
                # if the hours agg only contains "-" plaything entries, they are all "nil activity" records
                pt_names = hours_df.plaything_name.unique()
                if (len(pt_names) == 1) and (pt_names[0] == "-"):
                    rec = {"tag": "-", "plaything_name": "-", "plaything_part": "-", "specification_id": "-", "date": d, "start_ts": d_start_ts, "count": 0, "sessions": 0, "partition_key": "1"}
                    ac.aggregated_container.create_item(rec, enable_automatic_id_generation=True)
                else:
                    # zero-hour placeholders should be removed before creating day sums
                    for ix, group in hours_df.loc[hours_df.plaything_name != "-"].groupby(by=["tag", "plaything_name", "plaything_part", "specification_id"]):
                        rec = group.iloc[0][["tag", "plaything_name", "plaything_part", "specification_id"]].to_dict()
                        rec.update(group[["count", "sessions"]].sum(axis=0).to_dict())
                        rec.update({"date": d, "start_ts": d_start_ts, "partition_key": "1"})  # force single partition
                        ac.aggregated_container.create_item(rec, enable_automatic_id_generation=True)
                logging.info(f"Completed date aggregation for {d}.")

            # prep for next iter
            start_ts += 3600
            n_updates += 1
        logging.info(f"Completed {n_updates} hour aggregations. Last covered timestamp = {end_ts}.")

if __name__ == "__main__":
    aggregator()
