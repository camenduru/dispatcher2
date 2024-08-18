import http.server
import socketserver
import os
import json
import requests
import threading
from pymongo import MongoClient

mongodb_uri = os.getenv('com_camenduru_mongodb_uri')
worker_uri = os.getenv('com_camenduru_worker_uri')
runpod_token = os.getenv('com_camenduru_runpod_token')
job_type = os.getenv('com_camenduru_job_type')
job_sources = os.getenv('com_camenduru_job_source', '').split(':')
server_port = os.getenv('com_camenduru_server_port')

def loop():
    client = MongoClient(mongodb_uri)
    db = client['web2']
    collection_job = db['job']

    def check_jobs():
        waiting_documents = collection_job.find({"status": "WAITING", "source": {"$in": job_sources}})
        for waiting_document in waiting_documents:
            server = waiting_document['type']
            if(server==job_type):
                command = waiting_document['command']
                notify_uri = waiting_document['notify_uri']
                notify_token = waiting_document['notify_token']
                discord_id = waiting_document['discord_id']
                discord_channel = waiting_document['discord_channel']
                discord_token = waiting_document['discord_token']
                job_id = waiting_document['_id']
                collection_job.update_one({"_id": job_id}, {"$set": {"status": "WORKING"}})
                command_data = json.loads(command)
                command_data["notify_uri"] = notify_uri
                command_data["notify_token"] = notify_token
                command_data["discord_id"] = discord_id
                command_data["discord_channel"] = discord_channel
                command_data["discord_token"] = discord_token
                command_data['job_id'] = str(job_id)
                data = { "input": command_data }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {runpod_token}"
                }
                try:
                    requests.post(worker_uri, headers=headers, json=data)
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")

        threading.Timer(1, check_jobs).start()
    check_jobs()

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = super().translate_path(path)
        if path.endswith('.py'):
            self.send_error(404, "File not found")
            return None
        return path
      
PORT = int(server_port)
Handler = MyHandler
Handler.extensions_map.update({
    '.html': 'text/html',
})

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    thread = threading.Thread(target=loop)
    thread.start()
    httpd.serve_forever()