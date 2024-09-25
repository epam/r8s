from init_minio import init_minio
from init_vault import init_vault
from init_mongo import init_mongo
from init_system_user import init_system_user

init_minio()
init_vault()
init_mongo()
init_system_user()
