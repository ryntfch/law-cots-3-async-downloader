from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from make_celery import make_celery
from subprocess import Popen, PIPE
from functools import partial
from os.path import basename
from threading import Thread
import zlib
import uuid
import pika
import zipfile
import io
import os
import time
import sys
import types
import json
import wget


app = Flask(__name__)
app.config.from_pyfile('settings.py')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def download_file(url, unique_id, route_key):

    time.sleep(1)

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=app.config['MQ_HOST'],
            port=app.config['MQ_PORT'],
            virtual_host="/"+app.config['MQ_VHOST'],
            credentials=pika.PlainCredentials(
                username=app.config['MQ_USERNAME'],
                password=app.config['MQ_PASSWORD']
            ),
        ))
    channel = connection.channel()
    channel.exchange_declare(
        exchange=app.config['MQ_EXCHANGE_KEY'], exchange_type='direct')

    def send_message(message, route_key, exchange_key=app.config['MQ_EXCHANGE_KEY']):

        channel.basic_publish(exchange=exchange_key,
                              routing_key=route_key,
                              body=message)

        print("\n [x] Sent %r\n" % message)

    def bar_custom(current, total, width=80):
        message = '{"status": "on_progress", "percentage": ' + \
            str(round(current / total * 100, 2)) + '}'
        send_message(message, route_key)

    file_name = wget.download(url, 
                    bar=bar_custom, out="downloads")

    message = '{"status": "on_progress", "percentage": ' + \
        str(100) + '}'

    send_message(message, route_key)

    time.sleep(0.2)

    message = '{"status": "completed", "message" : "Your file has been downloaded!", "url": ' + '"' + \
        f"{app.config['UC_URL']}/{file_name}" + '"' + '}'

    send_message(message, route_key)

    connection.close()
    return


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "url" not in request.form:
            return jsonify({"message": "put your url", "status_code": 403})

        url = request.form["url"]
        route_key = request.headers.get('X-ROUTING-KEY')

        if url == "" or route_key == "":
            return jsonify({"message": "forbidden", "status_code": 403})

        unique_id = uuid.uuid1()

        res = {
            "unique_id": unique_id,
            "message": "Download Executed!",
            "status_code": 200,
        }

        thread = Thread(target=download_file, args=(
            url,
            unique_id,
            request.headers.get('X-ROUTING-KEY')
        ))

        thread.daemon = True
        thread.start()

        return jsonify(res)

    else:
        return jsonify({"sanity": "checked"})


@app.route("/downloads/<filename>")
def uploaded_file(filename):
    return send_from_directory("downloads", filename)

# Or specify port manually:
if __name__ == "__main__":
    port = int(os.environ.get("COMPRESS_SERVICE_PORT", 8081))
    app.run(host="0.0.0.0", port=port)
