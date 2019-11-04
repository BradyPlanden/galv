# Galvanalyser project

Folder Structure
----------------
```
├── config -- Has an example harvester config in, can be used to store test harvester configs locally
├── galvanalyser -- The python code goes here, all under the galvanalyser namespace
│   ├── database -- Library files for interacting with the database
│   ├── harvester -- The harvester app
│   ├── protobuf -- Automatically generated protobuf python code
│   └── webapp -- The webapp
│       ├── assets -- Static files here are served by the webapp. The JS files that handle dash callbacks client side are here
│       ├── datahandling -- Python flask route handlers for handling requests to query the database
│       └── pages -- Files describing the webapp pages
├── harvester -- Harvester docker file
├── libs -- assorted dependency libraries
│   ├── closure-library -- google library, used for building the single js file for protobufs and dependencies, provides AVL Tree data structure
│   ├── galvanalyser-js-protobufs  -- Automatically generated protobuf javascript code
│   └── protobuf -- google protobuf library
├── protobuf -- definition of the protobufs used in this project
├── tests -- Tests (these are old and may not work anymore and aren't proper unit tests)
├── webapp-static-content -- Static content
│   ├── js -- The js file here gets bundled into the file generated by the closure-library
│   └── libs -- The automatically generated js file made by closure-library gets put here. This is served by nginx
└── webstack -- Docker-compose things go here
    ├── dashapp -- The dockerfile for the web app
    ├── database -- The sql file for setting up the database (should probably move elsewhere)
    └── nginx-config -- The nginx config file lives here
```
## The Makefile
There are several scripts in the Makefile that are useful

## make update-submodules
Checks out the git submodules or updates them if necessary.

### make format
The format script formats all the python and javascript files for consistent formatting

### make builder-docker-build
This builds the "builder" docker image. This is a docker image that can be used for cross platform building of this project.

### make builder-docker-run
This runs the builder docker image. It mounts the project directory in the builder docker container and the builder docker then runs the builder/build.sh script. This should generate the protobuf and library files used by the project in the appropriate places in this project
on your local file system.

### make protobuf
This builds the protobuf files for javascript and python.
It also bundles up some JS modules and the built javascript protobufs into a single file to be served to web clients.

### make harvester-docker-build
Builds the harvester docker image

### make harvester-docker-run
Runs the harvester docker image. The paths in this will need to change since there are a couple of absolute ones to directories on my machine.

### make test
Runs some old broken tests. It'd be good to fix this some time.

### make init
pip installs the python requirements. See Setup.

## Setup
If you want to run things locally - not in a docker
```
# make a virtual environment
python3 -m venv ./.venv
# run the init script in the Makefile to pip install all the requirements
make init
```

## Running the server
In the `webstack` directory run `docker-compose up`

## Database setup
There is a file `webstack/database/setup.pgsql` that describes the database

## Harvester config
For the harvester that runs in a docker you can create a `harvester-config.json` file in the `config` directory with some content that looks like
```
{
    "database_name": "galvanalyser", 
    "database_port": 5432, 
    "database_username": "harvester_user", 
    "database_password": "harvester_password", 
    "machine_id": "test_machine_01", 
    "database_host": "127.0.0.1",
    "institution": "Oxford"
}
```
You'll want to add a harvester user to the database
```
CREATE USER harvester_user WITH
  LOGIN
  NOSUPERUSER
  INHERIT
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
  PASSWORD 'harvester_password';

GRANT harvester TO harvester_user;
```

## Setting up for the first time
The following are some example commands you'd need to run to get started. This assumes you have `make`, docker and docker-compose installed
```
# Download the submodules
make update-submodules

# Build the builder docker image
make builder-docker-build

# Build the webstack
make build-webstack

# Configure where the postgres docker stores the data by editing PG_DATA_PATH in webstack/.env

# Next start the webstack
cd webstack
docker-compose up

# Now connect to the database and use the following to set it up
# Create the galvanalyser database with the 'CREATE DATABASE' statement at the start of webstack/database/setup.pgsql
# Run all the sql after the 'CREATE DATABASE' statement in that file in the galvanalyser database.

# Now setup the following as appropriate to your setup.

# Create one or more harvester users as described in the 'Harvester config' section above.

# Add one or more harvesters to the harvesters table. The names given should match the name you use in the harvester config.
# Here we're using 'test_machine_01' to match the name in the 'Harvester config' section above.
INSERT INTO harvesters.harvester (machine_id) VALUES ('test_machine_01');

# Create an institution entry for your institution e.g.
INSERT INTO experiment.institution (name) VALUES ('Oxford');
# The name you use should match the name in your harvester config json files

# Create some users
CREATE USER alice WITH
  LOGIN
  NOSUPERUSER
  INHERIT
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
  PASSWORD 'alice_pass';
GRANT normal_user TO alice;

CREATE USER bob WITH
  LOGIN
  NOSUPERUSER
  INHERIT
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
  PASSWORD 'bob_pass';
GRANT normal_user TO bob;

# Register some directories for the harvester to monitor.
# The 1 here is the id number of the harvester created earlier in the harvesters.harvester
# Specify one path per row, you can specify multiple users to receive read permissions for uploaded data
INSERT INTO harvesters.monitored_path (harvester_id, path, monitored_for) VALUES (1,'/usr/src/app/test-data', '{alice}');
INSERT INTO harvesters.monitored_path (harvester_id, path, monitored_for) VALUES (1,'/some/other/path/data', '{alice, bob}');

# With your database setup you can run the harvester.
# You can setup the harvester on another machine in which case you don't need to build the webstack or even get the submodules.
# You only need to setup the harvester-config.json and the following.
# There are two ways you can run the harvester, you can either use a python venv or a docker image.

# To use the docker image
make harvester-docker-build
# Edit the 'harvester-docker-run' command in the make file to mount the correct config and data directories in the docker container and then run it with
make harvester-run

# To run in a venv use
make init
make harvester-run
# Note in this case teh harvester will be looking for its config at ./config/harvester-config.json 

```