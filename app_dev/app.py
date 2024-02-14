import os
import json
from promptflow import PFClient, load_flow
from promptflow.entities import AzureOpenAIConnection, CognitiveSearchConnection
from dotenv import load_dotenv

def main(): 
        
    try: 
        # Get configuration settings 
        load_dotenv()
        azure_oai_endpoint = os.getenv("AZ_OAI_ENDPOINT")
        azure_oai_key = os.getenv("AZ_OAI_KEY")
        azure_oai_chat_deployment = os.getenv("AZ_OAI_CHAT_DEPLOYMENT_NAME")
        azure_oai_embeddings_deployment = os.getenv("AZ_OAI_EMBEDDINGS_DEPLOYMENT_NAME")
        azure_oai_version = os.getenv("AZ_OAI_API_VERSION")
        azure_aisearch_key = os.getenv("AZ_AISEARCH_ADMIN_API_KEY")
        azure_aisearch_endpoint = os.getenv("AZ_AISEARCH_ENDPOINT")
        azure_aisearch_index = os.getenv("AZ_AISEARCH_INDEX_NAME")

        pf = PFClient()

        # Initialize an Azure OpenAI Connection object
        azure_oai_connection = AzureOpenAIConnection(
            name="azure_open_ai_connection", 
            api_key=azure_oai_key, 
            api_base=azure_oai_endpoint,
            api_version=azure_oai_version
        )

        # Initialize Azure AI Search Connection
        azure_ai_search_connection = CognitiveSearchConnection(
            name="azure_ai_search_connection",
            api_key=azure_aisearch_key,
            api_base=azure_aisearch_endpoint,
        )

        # Create the Azure OpenAI connection, note that api_key will be 
        # scrubbed in the returned result
        result = pf.connections.create_or_update(azure_oai_connection)
        print(result)

        # Create the Azure AI Search connection, note that api_key will be 
        # scrubbed in the returned result
        result = pf.connections.create_or_update(azure_ai_search_connection)
        print(result)

        # Set flow path and run input data
        flow="rag-flow" # set the flow directory name

        history = []
        with open('rag-flow/chat_history.json') as f:
                history = json.load(f)

        while True:
            question = input("\033[92m" + "$User (type q! to quit): " + "\033[0m")
            if question == "q!":
                break

            # Test flow
            inputs = {
                "question": question,
                "chat_deployment_name":azure_oai_chat_deployment,
                "embeddings_deployment_name":azure_oai_embeddings_deployment,
                "search_index_name":azure_aisearch_index,
                "chat_history": history
                }  # The inputs of the flow.
            flow_result = pf.test(flow=flow, inputs=inputs)
            print(f"Flow outputs: {flow_result}")
            
            new_history = {
                "inputs" : 
                {
                    "chat_input" : question
                }, 
                "outputs": 
                {
                    "chat_output" : flow_result["chat_output"]
                }
            }
            history.append(new_history)

            print(history)

    except Exception as ex:
        print(ex)

if __name__ == '__main__': 
    main()