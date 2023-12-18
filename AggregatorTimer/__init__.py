import azure.functions as func
from aggregator import aggregator
import logging

def main(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.info('The timer is past due!')
    aggregator()
