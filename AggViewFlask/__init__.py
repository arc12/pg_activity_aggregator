import logging

from flask import Flask, render_template, session, request, abort, Blueprint, redirect

from pg_shared import prepare_app
from pg_shared.dash_utils import add_dash_to_routes
from AggViewFlask.dash_apps import dash_basic
from agg_view import AT_NAME, core, Langstrings, menu

at_root = core.at_root

# Using a blueprint is the neatest way of setting up a URL path which starts with the plaything name (see the bottom, when the blueprint is added to the app)
# This strategy would also allow for a single Flask app to deliver more than one plaything, subject to some refactoring of app creation and blueprint addition.
pt_bp = Blueprint(AT_NAME, __name__, template_folder='templates')

@pt_bp.route("/")
def index():
    # redirect to about, preserving the lang query string param
    lang = request.args.get('lang')
    if lang is None or lang == '':
        lang="en"
        
    return redirect(f'{at_root}/about?lang={lang}')

@pt_bp.route("/ping")
def ping():
    return "OK"

@pt_bp.route("/about", methods=['GET'])
def about():
    view_name = "about"

    lang = request.args.get('lang')
    if lang is None or lang == '':
        lang="en"
    langstrings = Langstrings(lang)

    return render_template("about.html",
                           about=core.load_asset_markdown(view_name, lang, render=True),
                           top_menu=core.make_menu(menu, langstrings, at_root, view_name, query_string=request.query_string.decode()))


app = prepare_app(Flask(__name__), url_prefix=at_root)
app.register_blueprint(pt_bp, url_prefix=at_root)

# DASH Apps and route spec. NB these do need the URL prefix
add_dash_to_routes(app, dash_basic, at_root, with_specification_id=False)
