#import os
import sqlite3
import warnings
import pyttsx3
import json
from typing import Optional
from langchain.agents import initialize_agent, Tool, AgentType
from langchain_groq import ChatGroq
from langchain.memory import ConversationBufferWindowMemory
from langchain.memory.chat_message_histories import FileChatMessageHistory
from langchain.agents.mrkl.output_parser import MRKLOutputParser
from pymongo import MongoClient

warnings.filterwarnings("ignore")

# Global variable to store the authenticated employee id.
authenticated_employee_id = None

class CustomOutputParser(MRKLOutputParser):
    def parse(self, text: str):
        try:
            return super().parse(text)
        except Exception:
            return {"final_answer": text}

# Initialize the TTS engine
engine = pyttsx3.init()

def speak(text: str):
    """Convert text to speech and play it."""
    engine.say(text)
    engine.runAndWait()

# ----------------------------
# 1. Set Up a Simple HR Database
# ----------------------------
def setup_db():
    """Creates an in-memory SQLite database with a sample employees table."""
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute("CREATE TABLE employees (employee_id TEXT PRIMARY KEY, leave_balance INTEGER)")
    # Insert sample data.
    c.execute("INSERT INTO employees VALUES ('EMP123', 15)")
    c.execute("INSERT INTO employees VALUES ('EMP456', 10)")
    conn.commit()
    return conn

db_conn = setup_db()

# Replace <username> and <password> with your credentials.
MONGO_URI = "mongodb+srv://adithyadnayak:4yvB4AZ4pGGhVTrR@employee.aqtf1.mongodb.net/?retryWrites=true&w=majority&appName=Employee"
client = MongoClient(MONGO_URI)
db = client["Company"]
employees_collection = db["Employees"]

# ----------------------------
# 2. User Authentication and Memory Setup
# ----------------------------
def login():
    """A simple login function that verifies the employee id and password.
       For demonstration, we assume that the MongoDB collection 'Employees'
       contains documents with fields 'id' and 'password'.
    """
    global authenticated_employee_id
    print("Please log in to continue.")
    employee_id = input("Enter your employee ID: ").strip()
    password = input("Enter your password: ").strip()
    
    # In production, ensure passwords are hashed and use secure comparison.
    employee = employees_collection.find_one({"id": employee_id, "password": password})
    if employee:
        authenticated_employee_id = employee_id
        print("Login successful.")
        return employee_id
    else:
        print("Invalid credentials. Exiting.")
        exit(1)

def create_memory_for_user(employee_id: str):
    """Creates a FileChatMessageHistory specific to the employee."""
    history_file = f"chat_history_{employee_id}.txt"
    return ConversationBufferWindowMemory(
        memory_key="chat_history",
        return_messages=True,
        chat_memory=FileChatMessageHistory(history_file)
    )

# ----------------------------
# 3. Define the Tools with Access Control
# ----------------------------
def leave_balance_query(employee_id: str) -> str:
    """Queries the HR database for the leave balance of the authenticated employee.
       Prevents users from querying others' data.
    """
    if employee_id != authenticated_employee_id:
        return "Access Denied"
    c = db_conn.cursor()
    c.execute("SELECT leave_balance FROM employees WHERE employee_id = ?", (employee_id,))
    row = c.fetchone()
    if row:
        return f"Employee {employee_id} has {row[0]} vacation days remaining."
    else:
        return f"No record found for employee {employee_id}."

def policy_lookup(query: str) -> str:
    """Retrieves an HR policy from a text file."""
    try:
        with open("policies.txt", "r", encoding="utf-8") as f:
            policies = dict(line.strip().split(": ", 1) for line in f if ": " in line)
        return policies.get(query.lower(), "Policy not found. Please ask about vacation, healthcare, promotion, onboarding, or benefits.")
    except FileNotFoundError:
        return "Policy file not found. Please ensure policies.txt exists."
    
def get_employee_details(employee_id: str) -> str:
    """Fetch employee details from MongoDB but only for the authenticated employee."""
    if employee_id != authenticated_employee_id:
        return "Access Denied"
    employee = employees_collection.find_one({"id": employee_id})
    if employee:
        return f"Employee {employee_id} details: {employee}"
    return f"No record found for employee {employee_id}."
    
def store_user_info(info: str) -> str:
    """Stores important user information in memory."""
    memory.save_context({"input": info}, {"output": f"Got it! I'll remember that: {info}"})
    return f"I've saved this information: {info}"

def retrieve_memory(_input: str) -> str:
    """Retrieves the conversation memory."""
    return f"Here's what I remember from our conversation:\n{memory.load_memory_variables({})['chat_history']}"

#def clear_memory(_input: str = None) -> str:
    """Clears all stored memory."""
    #memory.clear()  # Reset the conversation history and any stored data.
    #return "All memory has been erased."

#def clear_memory(file_path: str = None) -> str:
    """Erases all data from the specified text file."""
   # with open(file_path, 'w') as file:
    #    pass  # This effectively clears the file content


def clear_memory(file_path: str) -> str:
    """Replaces the content of a text file with a preset JSON structure containing the employee ID extracted from the file name."""
    if not file_path or "EMP" not in file_path:
        return "Invalid file name. Please use the format chat_history_EMP123.txt"

    # Extract employee ID from file name
    employee_id = file_path.split("_")[-1].split(".")[0]

    data = [
        {"type": "human", "data": {"content": f"Employee id is {employee_id}", "additional_kwargs": {}, "response_metadata": {}, "type": "human", "name": None, "id": None, "example": False}},
        {"type": "ai", "data": {"content": f"Got it! I'll remember that: Employee id is {employee_id}", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": None, "id": None, "example": False, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": None}},
        {"type": "human", "data": {"content": f"Store the employee id if it's the first time you see this: Employee id: {employee_id}", "additional_kwargs": {}, "response_metadata": {}, "type": "human", "name": None, "id": None, "example": False}},
        {"type": "ai", "data": {"content": "Hello! I'm HRBot, your friendly HR assistant. How can I help you today?", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": None, "id": None, "example": False, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": None}}
    ]
    
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

    return f"Chat history for {employee_id} has been reset."

def show_memory(_input: str = None) -> str:
    """Displays all stored memory data for debugging."""
    memory_data = memory.load_memory_variables({})
    return memory_data if memory_data else "No memory stored."


tools = [
    Tool(
        name="Leave Balance Check",
        func=lambda input: leave_balance_query(input.split()[-1]),
        description=(
            "Useful for checking your leave balance. When a user says something like 'leave balance EMP123', "
            "this tool should be called. Note: you can only query your own employee id."
        )
    ),
    Tool(
        name="HR Policy Lookup",
        func=policy_lookup,
        description=(
            "Useful for retrieving HR policies. When a user asks about policies such as 'vacation', 'healthcare', "
            "or 'promotion', this tool should be called. The input should be a single keyword."
        )
    ),
    Tool(
        name="Employee Details Lookup",
        func=lambda input: get_employee_details(input.split()[-1]),
        description=(
            "Retrieve your own employee details from MongoDB using your employee ID. "
            "Use it if you need to check user details like name, email, age, etc." 
            "The input should be a single keyword. Only the employee id in the format 'EMP123' is allowed."       
        )
    ),
    Tool(
        name="Store Information",
        func=store_user_info,
        description="Store user details such as name, department, or preferences. Input should be a sentence describing the information."
    ),
    Tool(
        name="Retrieve Memory",
        func=retrieve_memory,
        description="Retrieve stored conversation details. Input can be anything."
    ),
    Tool(
        name="Clear Memory",
        func=clear_memory,
        description="Clears all stored conversation history and user information. Input should be of the format chat_history_EMP123.txt. Replace EMP123 with your employee id. If you're not sure about the employee id, use the Retrieve Memory tool."
    ),
    Tool(
        name="Show Memory",
        func=show_memory,
        description="Displays all stored memory data for debugging."
    ),
]

# ----------------------------
# 4. Initialize the Groq LLM and the Agent with a System Prompt
# ----------------------------
agent_kwargs = {
    "prefix": (
        "You are HRBot, a friendly and professional HR assistant. "
        "Your responsibilities include answering questions about company policies, leave balances, onboarding, benefits, etc. "
        "If a user provides their name (for example, 'my name is adi'), remember it and address them by name in future responses. "
        "Don't answer any questions that are out of context or inappropriate. Politely decline to answer and tell the user to ask you about HR-related topics. "
        "Use the available tools when appropriate. "
        "If you try to retrieve memory and nothing comes up, check the employee records first using the Employee Details Lookup tool and if you still dont find it, then ask the user for the info and use the store information tool. "
        "Don't clear memory more than once at a time. "
        "If you need to know any information about the user like for example their name, check with the Employee Details Lookup tool first. Check your memory with the Retrieve memory tool to get the user's employee id and use the id to search for the user's details. If you can't find what you need, ask the user. "
        "If you get the output: Access denied when you tried to look up some employee details, tell the user that they can only check their own records. Don't try to access any other details until said to do so. "
        "If the user asks to clear memory, use the Retrieve Memory tool to get the file path and use the Clear Memory tool to clear the memory. "
    )
}

llm = ChatGroq(
    temperature=0.7,
    model_name="llama3-70b-8192"
)

# The memory will be created after login (see below).
memory = None

# ----------------------------
# 5. Run the Chatbot with Authentication
# ----------------------------
def hr_chatbot():
    global memory
    # Authenticate the user.
    user_id = login()
    # Create a user-specific memory instance.
    memory = create_memory_for_user(user_id)
    # Now initialize the agent with the user-specific memory.
    agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        agent_kwargs=agent_kwargs,
        memory=memory,
        # output_parser=CustomOutputParser()  # Uncomment if you need the custom parser.
    )

    agent.run("Store the employee id if it's the first time you see this: Employee id: " + user_id)
    print("HRBot: Hello! I'm your HR assistant. How can I help you today?")
    speak("Hello! I'm your HR assistant. How can I help you today?")
    
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            farewell = "Thank you for using HR services!"
            print(f"HRBot: {farewell}")
            speak(farewell)
            break

        # The agent processes the query using the persistent user-specific memory.
        response = agent.run(user_input)
        print(f"HRBot: {response}")
        speak(response)

if __name__ == "__main__":
    hr_chatbot()
