# Winter Sports Performance Engine

A modular pipeline for scraping, cleaning, structuring, and modeling winter sports performance data.  
Phase 1 begins with cross-country skiing (XC), later extendable to biathlon, ski jumping, alpine, and Nordic combined.

## Project Structure

src/
scraping/ # Downloading & caching race results
parsing/ # Converting raw HTML/CSV into structured tables
cleaning/ # Standardizing names, nations, times, removing errors
features/ # Form scores, trends, athlete ratings
utils/ # Shared utilities (time parsing, config, matching)
pipelines/ # Scripts to generate master tables and dataset splits
data_raw/ # Raw scraped dumps (kept for reproducibility)
data_clean/ # Cleaned, normalized datasets
models/ # Trained ML models
notebooks/ # Exploratory analysis, validation


## Goals (Phase 1)

1. Automatic scraping of race results  
2. Standardized and clean master dataset  
3. Athlete identity resolution  
4. Form/Trend/Ratings feature library  
5. ML-ready training dataset 


