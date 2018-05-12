# simple_fb_clone
Sample project for Cloud Computing course homework 2.

This is a Python Flask project. This project connects to a MongoDB NoSQL database.

Create a "database.config" file, you need to specify connection string and target schema name for the application like below:

> connection_string = <mongodb_connection_string_here>

> schema_name = <schema_name_here>

To run this Python Flask project, follow instructions in below link first:
http://flask.pocoo.org/docs/1.0/installation/

After virtual environment installation, install following packages:
> pip install pymongo
> pip install flask

In the end, run application with following command:
> python app.py
