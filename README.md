# Bring Your SharePoint Online Data in Azure OpenAI (RAG Application)

This repository shows how to generate vector embeddings from SharePoint Online site's documents (PDF or Word), store them in search indexes in Azure AI Search, and use the results to formulate a response in the Azure OpenAI chat completions.

This is a manual step-by-step guide and does not have production automation built in. This is meant to help understand the process of building a Retreival Augement Generate (RAG) app on SharePoint/Teams uploaded files instead of being deployment ready.

## Personas

In order to use this repo, it is split into two separate personas to complete the tasks required. View the corresponding folder for your role:
- [Application developer/data scientist](tree/main/app_dev)
- [SharePoint administrator](tree/main/sharepoint_admin)

## Known limitations

Currently this approach does not allow the following:
- <b>Folder and/or file filters</b>: This approach does not limit indexing to specific documents or folders within a SharePoint site. In the future, we will look into adding support for [SharePoint embedded](https://learn.microsoft.com/en-us/sharepoint/dev/embedded/overview) which offers this level of access granularity.

## Credit
Part of this repository is build on top of the work and insights found in https://github.com/liamca/sharepoint-indexing-azure-cognitive-search