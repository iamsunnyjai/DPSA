import requests
import time
import os
import sys

import openai
from langchain.chains import ConversationalRetrievalChain, RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
from langchain.indexes.vectorstore import VectorStoreIndexWrapper
from langchain.llms import OpenAI
from langchain.vectorstores import Chroma

from utils import config_util as cfg
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

httpproxy = '127.0.0.1:7890' 
proxy_flag = '1' 

def question(cont):

    os.environ["OPENAI_API_KEY"] = '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'

    # Enable to save to disk & reuse the model (for repeated queries on the same data)
    PERSIST = False

    query = None
    if len(sys.argv) > 1:
        query = sys.argv[1]

    if PERSIST and os.path.exists("persist"):
        vectorstore = Chroma(persist_directory="persist", embedding_function=OpenAIEmbeddings())
        index = VectorStoreIndexWrapper(vectorstore=vectorstore)
    else:
        #loader = TextLoader("data/data.txt") # Use this line if you only need data.txt
        loader = DirectoryLoader("ai_module/data/")
    if PERSIST:
        index = VectorstoreIndexCreator(vectorstore_kwargs={"persist_directory":"persist"}).from_loaders([loader])
    else:
        index = VectorstoreIndexCreator().from_loaders([loader])

    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(model="gpt-3.5-turbo"),
        retriever=index.vectorstore.as_retriever(search_kwargs={"k": 1}),
        verbose=True
    )
    
    chat_history = []
    result = chain({"question": cont, "chat_history": chat_history})
    chat_history.append((query, result['answer']))
    response_text = result['answer']

    return response_text

if __name__ == "__main__":
    #test proxy
    for i in range(3):
        
        query = "what is nlp"
        response = question(query)        
        print("\n The result is ", response)    