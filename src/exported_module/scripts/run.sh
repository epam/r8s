#!/bin/bash

echo "Creating MongoDB indexes"
python exported_module/scripts/init_mongo.py

echo "Creating the necessary buckets in Minio"
python exported_module/scripts/init_minio.py

echo "Creating the necessary engine and token in Vault"
python exported_module/scripts/init_vault.py

echo "Starting the server"
nohup python main.py