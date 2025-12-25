from pymongo import MongoClient
import os

# -------------------- VARIÁVEIS DE AMBIENTE --------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017") # URI do MongoDB
MONGO_DB = os.getenv("MONGO_DB") # Nome do banco
MONGO_STATUS_COLLECTION = os.getenv("MONGO_STATUS_COLLECTION", "status") # Nome da coleção
MONGO_UPDATES_COLLECTION = os.getenv("MONGO_UPDATES_COLLECTION", "updates") # Coleção de updates

# -------------------- CONEXÃO --------------------
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# Coleções
status_collection = db[MONGO_STATUS_COLLECTION]
updates_collection = db[MONGO_UPDATES_COLLECTION]

print(f"[MongoDB] Conectado ao banco '{MONGO_DB}' em {MONGO_URI}")
