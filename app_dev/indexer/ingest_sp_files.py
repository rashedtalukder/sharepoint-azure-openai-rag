import os
import json
import copy
from azure.core.credentials import AzureKeyCredential  
from azure.search.documents import SearchClient  
from azure.search.documents.indexes import SearchIndexClient 
from azure.search.documents.indexes.models import (  
    CorsOptions,
    HnswParameters,  
    HnswAlgorithmConfiguration,
    SimpleField,
    SearchField,  
    ComplexField,
    SearchFieldDataType,  
    SearchIndex,
    VectorSearch,  
    VectorSearchAlgorithmKind,  
    VectorSearchProfile,  
)
from dotenv import load_dotenv
from openai import AzureOpenAI
from semantic_kernel.text import text_chunker
from tenacity import retry, wait_random_exponential, stop_after_attempt

# Load environment variables from .env file
load_dotenv()

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def generate_embeddings(aoai_client, embeddings_deployment_name, text):
    '''
    Generate embeddings for title and content fields, also used for query embeddings
    '''
    response = aoai_client.embeddings.create(
        input=text,
        model=embeddings_deployment_name
    )
    return json.loads(response.model_dump_json())["data"][0]['embedding']

def divide_chunks(l, n):
    '''
    # Split a list into chunks. Used to reduce token count and increase relevancy for the LLM.
    '''
    # looping till length l  
    for i in range(0, len(l), n):   
        yield l[i:i + n]

def process_folders(folder_list, aoai_client, embeddings_model, ai_search_client, sp_extractor_client):
    total_docs_uploaded = 0
    n = 100  # batch size (number of docs) to upload at a time

    for folder in folder_list:
        '''
        Get the files in each of the the folders. Chunks the files for better search 
        results and reduced token counts. Generates embeddings for each document content 
        chunk, populates index fields, and uploads the JSON to Azure AI Search.

        NOTE: Demo only proccesses PDF and DOCX files, but can be expanded to other file 
        types.
        '''
        print (f"Processing folder {folder}...")

        if folder == '/':
            selected_files_content = sp_extractor_client.retrieve_sharepoint_files_content(
                site_hostname=os.environ["SP_SITE_HOSTNAME"],
                site_name=os.environ["SP_SITE_NAME"],
                file_formats=["docx", "pdf"],
            )
        else:
            selected_files_content = sp_extractor_client.retrieve_sharepoint_files_content(
                site_hostname=os.environ["SP_SITE_HOSTNAME"],
                site_name=os.environ["SP_SITE_NAME"],
                folder_path=folder,
                file_formats=["docx", "pdf"],
            )

        if selected_files_content == None:
            print ("No documents found in this folder")
        else:
            chunked_content_docs = []
            sfc_counter = 0
            for sfc_counter in range(len(selected_files_content)):
                chunked_content = text_chunker.split_plaintext_paragraph(
                    text=[selected_files_content[sfc_counter]['content']],
                    max_tokens=100
                )
                chunk_counter = 0
                for cc in chunked_content:
                    json_data = copy.deepcopy(selected_files_content[sfc_counter]) 
                    json_data['content'] = cc
                    json_data['contentVector'] = generate_embeddings( aoai_client, embeddings_model, json_data['content'])
                    json_data['doc_id'] = json_data['id']
                    json_data['id'] = json_data['id'] + "-" + str(chunk_counter)
                    json_data['chunk_id'] = chunk_counter
                    chunk_counter+=1
                    chunked_content_docs.append(json_data)
                sfc_counter+=1
                
            total_docs = len(chunked_content_docs)
            total_docs_uploaded += total_docs
            print (f"Total Documents to Upload: {total_docs}")

            for documents_chunk in divide_chunks(chunked_content_docs, n):  
                # Multiple Documents Upload
                try:
                    # 'ai_search_client.upload_documents' can ingest multiple documents at once
                    # 'selected_files_content' is a list of documents
                    print (f"Uploading batch of {len(documents_chunk)} documents...")
                    result = ai_search_client.upload_documents(documents=documents_chunk)
                    # Print the result for each document
                    for res in result:
                        print("Upload of document succeeded: ", res.succeeded)
                except Exception as ex:
                    print("Error in multiple documents upload: ", ex)
    return total_docs_uploaded
            

def upload_document_vectors():
    '''
    This function uploads the document vectors to Azure AI Search.
    '''
    # Instantiate the Azure AI Search client
    search_client = SearchClient(
        endpoint=os.environ["SEARCH_ENDPOINT"],
        index_name=os.environ["SEARCH_INDEX_NAME"],
        credential=AzureKeyCredential(os.environ["SEARCH_ADMIN_API_KEY"]),
    )

    # Instantiate the Azure OpenAI client
    aoai_client = AzureOpenAI(
        api_version=os.environ["AOAI_API_VERSION"],
        azure_endpoint=os.environ["AOAI_ENDPOINT"],
        api_key=os.environ["AOAI_KEY"]
    )

    embeddings_model = os.environ["AOAI_EMBEDDINGS_DEPLOYMENT_NAME"]

    from gbb_ai.sharepoint_data_extractor import SharePointDataExtractor

    # Instantiate the SharePointDataExtractor client
    # The client handles the complexities of interacting with SharePoint's REST API, providing an easy-to-use interface for data extraction.
    sp_extractor = SharePointDataExtractor()

    # Load environment variables from the .env file
    sp_extractor.load_environment_variables_from_env_file()

    # Authenticate with Microsoft Graph API
    sp_extractor.msgraph_auth()
    
    # Get the Site ID for the specified SharePoint site
    site_id = sp_extractor.get_site_id(
        site_hostname=os.environ["SP_SITE_HOSTNAME"], site_name=os.environ["SP_SITE_NAME"]
    )
    print(f"SharePoint Online Site Id: {site_id}" )

    # Get the Drive ID associated with the Site ID
    drive_id = sp_extractor.get_drive_id(site_id)

    # Use the access token to get the folders 
    print ('Getting all folders in SharePoint site...')
    
    folder_list = sp_extractor.get_site_folders(site_id=site_id)
    print(folder_list)

    num_uploaded = process_folders(folder_list, aoai_client, embeddings_model, search_client, sp_extractor)
    print (f"Upload of {num_uploaded} documents complete.")


def vector_search_config():
    '''
    This function defines the vector search configuration.
    '''
    return VectorSearch(  
        algorithms=[  
            HnswAlgorithmConfiguration(  
                name="myHnsw",  
                kind=VectorSearchAlgorithmKind.HNSW,  
                parameters=HnswParameters(  
                    m=4,  
                    ef_construction=400,  
                    ef_search=1000,  
                    metric="cosine",  
                ),  
            )
        ],  
    profiles=[  
            VectorSearchProfile(  
                name="myHnswProfile",  
                algorithm_configuration_name="myHnsw",  
            ),   
        ],  
    )

def index_fields_config():
    '''
    This function defines the fields in the index.
    '''
    return [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
            key=True,
        ),
        SimpleField(
            name="doc_id",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
            sortable=True,
            key=False,
        ),
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
            key=False,
        ),
        SearchField(
            name="name", type=SearchFieldDataType.String, filterable=True, sortable=True, analyzer_name="en.microsoft"
        ),
        SimpleField(
            name="created_datetime",
            type=SearchFieldDataType.DateTimeOffset,
            facetable=True,
            filterable=True,
            sortable=True,
        ),
        SearchField(
            name="created_by",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="size",
            type=SearchFieldDataType.Int32,
            facetable=True,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="last_modified_datetime",
            type=SearchFieldDataType.DateTimeOffset,
            facetable=True,
            filterable=True,
            sortable=True,
        ),
        SearchField(
            name="last_modified_by",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
        ),
        SimpleField(name="source", type=SearchFieldDataType.String),
        SearchField(
            name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"
        ),
        SearchField(
            name="contentVector",  
            hidden=False,
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single), 
            searchable=True,
            vector_search_dimensions=1536,  
            vector_search_profile_name ="myHnswProfile"
        ), 
        ComplexField(
                name="read_access_entity",
                collection=True,
                fields=[SimpleField(name="list_item", type=SearchFieldDataType.String, searchable=True, filterable=True,)],
                searchable=True),
    ]

def create_index():
    '''
    This function creates an index in Azure AI Search.
    '''

    # Set the service endpoint and API key from the environment
    # Create an SDK client
    index_client = SearchIndexClient(
        endpoint = os.environ["SEARCH_ENDPOINT"],
        index_name = os.environ["SEARCH_INDEX_NAME"],
        credential = AzureKeyCredential(os.environ["SEARCH_ADMIN_API_KEY"]),
    )

    # Delete an existing index with the name provided in the environment variables
    try:
        result = index_client.delete_index(os.environ["SEARCH_INDEX_NAME"])
        print("Index", os.environ["SEARCH_INDEX_NAME"], "deleted")
    except Exception as ex:
        print(ex)

    index = SearchIndex(
        name=os.environ["SEARCH_INDEX_NAME"],
        fields=index_fields_config(),
        scoring_profiles=[],
        suggesters=[{"name": "sg", "source_fields": ["name"]}],
        cors_options=CorsOptions(allowed_origins=["*"], max_age_in_seconds=60),
        vector_search=vector_search_config()
    )

    try:
        result = index_client.create_index(index)
        print("Index", result.name, "created")
        return True
    except Exception as ex:
        print(ex)
        return False


if __name__ == '__main__':
    if ( create_index()):
        upload_document_vectors()
