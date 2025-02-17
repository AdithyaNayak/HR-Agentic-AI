import os
from autogen import AssistantAgent, UserProxyAgent
#import pprint

# Configure Groq model
config_list = [{
    "model": "llama3-70b-8192",
    "api_key": os.environ.get("GROQ_API_KEY"),
    "api_type": "groq"
}]

     
# Create agent configurations
def create_agent(name, system_message):
    return AssistantAgent(
        name=name,
        llm_config={"config_list": config_list},
        system_message=system_message,
        is_termination_msg=lambda msg: "Terminate" in msg["content"]
    )

# Define specialized agents
hr_agent = create_agent(
    name="HR_Agent",
    system_message="You are an HR specialist. You answer questions about leave policies, employee benefits, workplace policies, and other HR-related topics. Respond ONLY to HR questions. End your output EXACTLY with Terminate.",
)

it_agent = create_agent(
    name="IT_Agent",
    system_message="You are an IT support specialist. You help with password resets, software issues, hardware problems, and other technical issues. Respond ONLY to IT-related questions. End your output EXACTLY with Terminate.",
)

# Create routing agent
router = create_agent(
    name="Router",
    system_message="""You are a Routing Agent. Analyze user queries and determine whether they should be handled by HR or IT. 
    Respond EXACTLY with either 'HR_Agent' or 'IT_Agent'. Do not include any other text in your response."""
)

# Create proxy agent for user interaction
user_proxy = UserProxyAgent(
    name="User_proxy",
    human_input_mode="NEVER",
    code_execution_config=False,
    default_auto_reply="",
    max_consecutive_auto_reply=1,
    is_termination_msg=lambda msg: "Terminate" in msg["content"]
)


# Function to log messages to a text file
def log_message(role, content, filename="chat_history_1.txt"):
    with open(filename, "a") as file:
        file.write(f"{role}: {content}\n")

# Define interaction workflow
def handle_query(user_input):
    # Log user input
    log_message("User", user_input)

    # First get routing decision
    user_proxy.initiate_chat(
        router,
        message=user_input,
        summary_method="last_msg",
        max_turns=1,
        clear_history=False  # Maintain conversation history
    )
    
    # Get the routing decision
    destination = user_proxy.last_message(router)["content"]
    
    # Route to appropriate agent
    if destination == "HR_Agent":
        user_proxy.initiate_chat(
            hr_agent,
            message=user_input,
            summary_method="last_msg",
            clear_history=False  # Maintain conversation history
        )
        response = user_proxy.last_message(hr_agent)["content"]
        
    elif destination == "IT_Agent":
        user_proxy.initiate_chat(
            it_agent,
            message=user_input,
            summary_method="last_msg",
            clear_history=False  # Maintain conversation history
        )
        response = user_proxy.last_message(it_agent)["content"]
        
    else:
        response = "I'm sorry, I couldn't determine the appropriate department to handle your query."
    
    # Log agent response
    log_message(destination, response)
    return response

# Main loop for continuous conversation
if __name__ == "__main__":
    print("Welcome to the support chat. Type 'exit' to end the conversation.")
    while True:
        query = input("You: ")
        if query.lower() == 'exit':
            print("Ending the conversation. Goodbye!")
            break
        response = handle_query(query)
        print(f"Agent: {response}")
