from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import boto3
import json
import os
import logging
import psycopg2
import uuid

# Get credentials from environment variables
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_name = os.getenv('DB_NAME')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')

# Connect to the database
conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    database=db_name,
    user=db_user,
    password=db_password
)

# Create a cursor object
cur = conn.cursor()

'''
PostgreSQL database structure

CREATE TABLE Users (
    user_id UUID UNIQUE PRIMARY KEY,
);

CREATE TABLE Conversations (
    conversation_id UUID UNIQUE PRIMARY KEY,
    user_id UUID REFERENCES Users(user_id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE Messages (
    message_id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES Conversations(conversation_id),
    user_id UUID REFERENCES Users(user_id),
    message_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Summaries (
    summary_id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES Conversations(conversation_id),
    user_id UUID REFERENCES Users(user_id),
    summary TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Emotions (
    emotion_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES Users(user_id),
    conversation_id UUID REFERENCES Conversations(conversation_id),
    happiness TEXT,
    sadness TEXT,
    fear TEXT,
    disgust TEXT,
    anger TEXT,
    surprise TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

'''

def insert_person(user_id):
    query = "INSERT INTO Users (user_id) VALUES (%s)"
    cur.execute(query, (user_id,))
    conn.commit() # DONE

# Insert conversation into Conversations table
def insert_conversation(conversation_id, user_id):
    query = "INSERT INTO Conversations (conversation_id, user_id) VALUES (%s, %s)"
    cur.execute(query, (conversation_id, user_id))
    conn.commit() # DONE

def insert_messages(conversation_id, user_id, message_type, content):
    query = 'INSERT INTO Messages (conversation_id, user_id, message_type, content) VALUES (%s, %s, %s, %s)'
    cur.execute(query, (conversation_id, user_id, message_type, content))
    conn.commit() # DONE

# Insert summary into Summaries table
def insert_summary(conversation_id, user_id, summary):
    query = "INSERT INTO Summaries (conversation_id, user_id, summary) VALUES (%s, %s, %s)"
    cur.execute(query, (conversation_id, user_id, summary))
    conn.commit() # DONE

# Insert sensitive information into SensitiveInformation table
# Replace 'category' with the actual name of the category
def insert_sensitive_info(user_id, conversation_id, category, user_input):
    query = f"INSERT INTO Emotions (user_id, conversation_id, {category}) \
              VALUES (%s, %s, %s)"
    cur.execute(query, (user_id, conversation_id, user_input))
    conn.commit() # DONE

# Retrieve conversation from Conversations table
def get_conversation(user_id):
    query = "SELECT m.content FROM Messages m WHERE m.user_id = %s"
    cur.execute(query, (user_id,))
    conversations = cur.fetchall()
    return conversations # DONE

# Retrieve summary from Summaries table
def get_summary(user_id):
    query = "SELECT s.summary FROM Summaries s WHERE s.user_id = %s"
    cur.execute(query, (user_id,))
    summary = cur.fetchone()
    return summary[0] if summary else None # DONE

# Retrieve sensitive information from SensitiveInformation table
def get_sensitive_info(user_id, category):
    query = f"SELECT e.{category} FROM Emotions e WHERE e.user_id = %s"
    cur.execute(query, (user_id,))
    info = cur.fetchone()
    return info[0] if info else 'no' # DONE

app = FastAPI()

user_id = str(uuid.uuid4())
conversation_id = str(uuid.uuid4())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sagemaker_runtime = boto3.client("sagemaker-runtime",
                                 aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                                 aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                                 region_name=os.environ.get("AWS_REGION"))

# Define SageMaker endpoints using environment variables
endpoints = {
    "llama": os.environ.get("LLAMA_ENDPOINT"),
    "topic_model": os.environ.get("TOPIC_MODEL_ENDPOINT"),
    "sentiment_analysis": os.environ.get("SENTIMENT_ANALYSIS_ENDPOINT")
}

logger.info(f"The llama endpoint: {endpoints['llama']}")
logger.info(f"The topic_model endpoint: {endpoints['topic_model']}")
logger.info(f"The sentiment model endpoint: {endpoints['sentiment_analysis']}")

# Dictionary to track conversation history
conversation_history = {}

# Mount the templates directory to serve static files
app.mount("/static", StaticFiles(directory="app/templates"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    logger.info("Saving the index page")
    with open("app/templates/index.html") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    insert_person(user_id)
    insert_conversation(conversation_id, user_id)
    while True:
        try:
            logger.info("Attempting to receive data...")
            data = await websocket.receive_text()
            logger.info (f"Received data: {data}")
            if data.strip():
                logger.info("Start the check_for_interruption function...")
                response, interrupt_flag = await check_for_interruption(data, conversation_history)
                logger.info("Check for interruption function is executed")
                await websocket.send_text(response if interrupt_flag else f"Interrupt: {response}")
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            await websocket.send_text(f"Error: {str(e)}")
            break

async def check_for_interruption(text, history):
    logger.info(f"Checking for interruption: {text}")
    logger.info("Invoking the topic model endpoint...")
    # Dummy topic list, replace with real topics
    candidate_labels = ["other", "sports", "technology", "health", "politics", "entertainment"]
    #call the topic model SageMaker endpoint
    topic_response = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoints["topic_model"],
        ContentType="application/json",
        Body=json.dumps({"inputs": text, "parameters": {"candidate_labels": candidate_labels}})
    )
    logger.info("Topic endpoint is successfuly executed")
    topic_result = json.loads(topic_response["Body"].read().decode())
    topic = topic_result["labels"][0]
    logger.info(f"The result topic is {topic_result}")

    logger.info("Invoking the sentiment model endpoint...")
    # call sentiment analysis model
    # label_1 == neutral; label_0 == negative; label_2 == positive
    sentiment_response = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoints["sentiment_analysis"],
        ContentType="application/json",
        Body=json.dumps({"inputs": text})
    )
    logger.info("The sentiment model endpoint is succsessfuly invoked.")
    sentiment_result = json.loads(sentiment_response["Body"].read().decode())
    sentiment = sentiment_result[0]["label"].lower()
    logger.info(f"Sentiment result: {sentiment}")

    if topic != 'other' and topic not in history and sentiment != 'label_1':
        history[topic] = {'label_2': False, 'label_0': False}
        history[topic][sentiment] = True
    
    insert_messages(conversation_id, user_id, message_type='user', content=text)
    

    if sentiment == 'label_1' or topic == 'other' or history[topic][sentiment]:
        logger.info("Invoking the llama2 model endpoint...")
        # No interruption needed, generate a response normally
        llama_response = sagemaker_runtime.invoke_endpoint(
            EndpointName=endpoints["llama"],
            ContentType="application/json",
            Body=json.dumps({"inputs": text})
        )
        logger.info("The llama2 model endpoint is successfully invoked.")
        llama_result = json.loads(llama_response["Body"].read().decode())
        response = llama_result[0]["generated_text"]
        insert_messages(conversation_id, user_id, message_type='ai', content=response)
        logger.info(f"The llama2 response: {response}")
        return response, False
    else:
        # Interruption needed
        for key in history[topic].keys():
            history[topic][key] = (key == sentiment)
        logger.info("Interruption detected.")
        response = "This seems inconsistent with your previous statements. Can you clarify?"
        insert_messages(conversation_id, user_id, message_type='ai', content=response)
        return "This seems inconsistent with your previous statements. Can you clarify?", True

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
