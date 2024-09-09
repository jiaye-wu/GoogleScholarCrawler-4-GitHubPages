# GoogleScholarCrawler-4-GitHubPages

A Google Scholar Crawler for GitHub Pages decoupled from [AcadHomepage](https://github.com/RayeRen/acad-homepage.github.io), a jekyll theme with **added features** of *i10-index* and *h-index* caching.

## Implementation

This crawler is decoupled from [AcadHomepage](https://github.com/RayeRen/acad-homepage.github.io) and it works well with [Academic Pages](https://github.com/academicpages/academicpages.github.io).

To try to implement it on your website:
    1. keep the folder structure and paste the files into your website root folder;
    2. in **project settings** > **Actions** > **General** > **Workflow permissions**, grant **Read and write permissions**;
    3. in **project settings** > Secret and variables > Actions > Repository Secrets > creat a key name ```GOOGLE_SCHOLAR_ID``` with value being *the string after your Google Scholar profile url* ```user=```;
    4. the crawler will create a branch in the website project named ```google-scholar-stats``` with 4 json files: ```gs_data.json``` (full data for all your papers), ```gs_data_hindex.json```, ```gs_data_i10.json```, and ```gs_data_shieldsio.json```. 
    5. If the crawler fails to do so, you can manually create a branch name ```google-scholar-stats``` from ```master```. The content in this branch will be permanantly cleared when the crawler is working.

## Display your Google Scholar Citation Badge

To use it **in your ```.md``` file** for your website pages:

### For **Google Scholar citation badge** 

Use ```<a href='https://scholar.google.com/citations?user=GOOGLE_SCHOLAR_ID'><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2F<your-github-user-name>%2F<your-github-user-name>.github.io@google-scholar-stats%2Fgs_data_shieldsio.json&labelColor=f6f6f6&color=9cf&style=flat&label=citations"></a>```, and it will be looking like <a href='https://scholar.google.com/citations?user=D2n8tswAAAAAJ'><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fjiaye-wu%2FGoogleScholarCrawler-4-GitHubPages@google-scholar-stats%2Fgs_data_shieldsio.json&labelColor=f6f6f6&color=9cf&style=flat&label=citations"></a>.

### For **Google Scholar h-index badge** 

Use ```<a href='https://scholar.google.com/citations?user=GOOGLE_SCHOLAR_ID'><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2F<your-github-user-name>%2F<your-github-user-name>.github.io@google-scholar-stats%2Fgs_data_hindex.json&labelColor=f6f6f6&color=9cf&style=flat&label=h-index"></a>```, and it will be looking like <a href='https://scholar.google.com/citations?user=D2n8tswAAAAAJ'><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fjiaye-wu%2FGoogleScholarCrawler-4-GitHubPages@google-scholar-stats%2Fgs_data_hindex.json&labelColor=f6f6f6&color=9cf&style=flat&label=h-index"></a>.

### For **Google Scholar i10-index badge** 

Use ```<a href='https://scholar.google.com/citations?user=GOOGLE_SCHOLAR_ID'><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2F<your-github-user-name>%2F<your-github-user-name>.github.io@google-scholar-stats%2Fgs_data_i10index.json&labelColor=f6f6f6&color=9cf&style=flat&label=i10-index"></a>```, and it will be looking like <a href='https://scholar.google.com/citations?user=D2n8tswAAAAAJ'><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fjiaye-wu%2FGoogleScholarCrawler-4-GitHubPages@google-scholar-stats%2Fgs_data_i10.json&labelColor=f6f6f6&color=9cf&style=flat&label=i10-index"></a>.

### All your other citation data for each paper

Available in ```gs_data.json```. You can be creative and do whatever you want with it!