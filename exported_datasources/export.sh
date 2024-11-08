#!/bin/bash

# Directory to store exported datasources
EXPORT_DIR="exported_datasources"
mkdir -p "$EXPORT_DIR"

# Fetch all datasources
datasources=$(curl -s -X GET "http://localhost:3000/api/datasources" \
    -H "Content-Type: application/json" \
    --user admin:admin)

# Loop over each datasource and export it
echo "$datasources" | jq -c '.[]' | while read -r datasource; do
    # Extract the datasource ID and name for the filename
    id=$(echo "$datasource" | jq -r '.id')
    name=$(echo "$datasource" | jq -r '.name' | sed 's/ /_/g')
    
    # Export the datasource configuration
    curl -s -X GET "http://localhost:3000/api/datasources/${id}" \
        -H "Content-Type: application/json" \
        --user admin:admin \
        -o "$EXPORT_DIR/${name}_datasource.json"
    
    echo "Exported datasource: ${name}"
done
