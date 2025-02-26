import os
import sqlite3
import warnings
from langchain.agents import initialize_agent, Tool, AgentType
from langchain_groq import ChatGroq
from langchain.memory import ConversationBufferWindowMemory
from langchain.memory.chat_message_histories import FileChatMessageHistory
from langchain.agents.mrkl.output_parser import MRKLOutputParser

warnings.filterwarnings("ignore")


class CustomOutputParser(MRKLOutputParser):
    def parse(self, text: str):
        try:
            return super().parse(text)
        except Exception:
            return {"final_answer": text}

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



from pymongo import MongoClient

# Replace <username> and <password> with your credentials
MONGO_URI = "mongodb+srv://adithyadnayak:4yvB4AZ4pGGhVTrR@employee.aqtf1.mongodb.net/?retryWrites=true&w=majority&appName=Employee"

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)

# Select the database
db = client["Company"]

# Select the collection
employees_collection = db["Employees"]

""""
# Fetch and print all employees
for employee in employees_collection.find():
    print(employee)"""


# ----------------------------
# 2. Define the Tools
# ----------------------------
def leave_balance_query(employee_id: str) -> str:
    """Queries the HR database for the leave balance of the given employee."""
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
    """Fetch employee details from MongoDB."""
    employee = employees_collection.find_one({"id": employee_id})
    if employee:
        return f"Employee {employee_id} details: {employee}"
    return f"No record found for employee {employee_id}."
    
# Store User Info in Memory
def store_user_info(info: str) -> str:
    """Stores important user information in memory."""
    memory.save_context({"input": info}, {"output": f"Got it! I'll remember that: {info}"})
    return f"I've saved this information: {info}"

# Retrieve Conversation Memory
def retrieve_memory(_input: str) -> str:
    """Retrieves the conversation memory."""
    return f"Here's what I remember from our conversation:\n{memory.load_memory_variables({})['chat_history']}"

# Clear Conversation Memory
def clear_memory(_input: str = None) -> str:
    """Clears all stored memory."""
    memory.clear()  # Reset the conversation history and any stored data
    return "All memory has been erased."

def show_memory(_input: str = None) -> str:
    """Retrieve and display all stored memory contents."""
    memory_data = memory.load_memory_variables({})  # Load stored data
    return memory_data if memory_data else "No memory stored."



tools = [
    Tool(
        name="Leave Balance Check",
        func=lambda input: leave_balance_query(input.split()[-1]),
        description=(
            "Useful for checking an employee's leave balance by accessing the HR database. "
            "When a user says something like 'leave balance EMP123', this tool should be called."
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
        description="Retrieve employee details from MongoDB using their employee ID."
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
        description="Clears all stored conversation history and user information."
    ),
    Tool(
        name="Show Memory",
        func=show_memory,
        description="Displays all stored memory data for debugging."
    )
]


# ----------------------------
# 3. Set Up Persistent Memory
# ----------------------------
# We use FileChatMessageHistory to persist conversation history to a file,
# and wrap it with ConversationBufferWindowMemory so that the agent can use the history.
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    return_messages=True,
    chat_memory=FileChatMessageHistory("chat_history.txt")
)

# ----------------------------
# 4. Initialize the Groq LLM and the Agent with a System Prompt
# ----------------------------
# The system prompt instructs HRBot to be friendly and professional, and to remember the user's name if provided.
agent_kwargs = {
    "prefix": (
        "You are HRBot, a friendly and professional HR assistant. "
        "Your responsibilities include answering questions about company policies, leave balances, onboarding, benefits, etc. "
        "If a user provides their name (for example, 'my name is adi'), remember it and address them by name in future responses. "
        "Don't answer any questions that are out of context or inappropriate. Politely decline to answer and tell the user to ask you about HR-related topics. "
        "Use the available tools when appropriate."
        "If you try to retrieve memory and nothing comes up, then ask the user for the info and use the store information tool."
        "Don't clear memory more than once at a time. "
    )
}

llm = ChatGroq(
    temperature=0.7,
    model_name="llama3-70b-8192"
)

# Initialize the agent with our tools, Groq LLM, system prompt, and persistent memory.
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    agent_kwargs=agent_kwargs,
    memory=memory,
    #output_parser=CustomOutputParser() 
)

# ----------------------------
# 5. Run the Chatbot
# ----------------------------


def hr_chatbot():
    print("HRBot: Hello! I'm your HR assistant. How can I help you today?")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("HRBot: Thank you for using HR services!")
            break

        # The agent processes the query using the persistent memory.
        response = agent.run(user_input)
        #response = output_parser(user_input)
        print(f"HRBot: {response}")

if __name__ == "__main__":
    hr_chatbot()
