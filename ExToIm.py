import requests
import json
import os
import datetime

# Configuration values
API_KEY = "<your-api-key>"  # Create one in immich under Account Settings
IMMICH_URL = "<your-immich-url>" # e.g. http://192.168.x.x:2283
LIBRARY_ID = "<your-external-library-id>" # UUID format string
CONTAINER_PATH_PRE = "/volume1/photo/" # can find this in immich under administration settings, external libraries
SYSTEM_PATH_PRE = "Y:/" # External library folder path as seen by the machine running this script
DELETE_FROM_TRASH = True # True will fully remove the asset (saving disk space / not recoverable), False will keep it in the Trash (where it still takes disk space but is recoverable)

# Do not change the values below (two different types of Headers are used for requests)
headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

headers2 = {
    "x-api-key": API_KEY,
    "Accept": "application/json"
}

# Function that returns a list of external libraries.
def get_libraries():
    libraries_list = f"{IMMICH_URL}/api/libraries"
    try:
        response = requests.get(libraries_list, headers=headers2)
        response.raise_for_status()
        libraries_result = response.json()
        print("""
The following external libraries were found. The py file should include the correct 'id' from this list.""")
        for library in libraries_result:
            print(f"   {library}")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Immich server: {e}")
        quit()
    except ValueError:
        print("Error decoding JSON response from Immich server.")
        quit()

def get_library_size():
    try:
        params = {
            'id': LIBRARY_ID
        }

        response = requests.get(f"{IMMICH_URL}/api/libraries/{LIBRARY_ID}/statistics", headers=headers, params=params)
        response.raise_for_status()

        library_size = round(response.json()["usage"] / (1024*1024),2) # size in bytes
        return library_size

    except requests.exceptions.RequestException as e:
        print(f"Error making API request to find external library statistics: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        quit()

# Function that returns a list of all assets within the chosen external library
def get_assets_list():
    try:
        page_no = 1 # the api returns a certain number of results per page
        ext_data = []   # the list to be returned

        print("\nFinding assets...")
        while page_no:
            search_criteria = {"libraryId": LIBRARY_ID, "page": page_no}
            response = requests.post(f"{IMMICH_URL}/api/search/metadata", headers=headers, json=search_criteria)
            response.raise_for_status()

            # response.json is structured as {"albums": {data}, "assets": {data} }
                # under assets, keys include "total", "count", "items" (this contains details on each asset), "facets", "nextPage"

            # add current page items to the list
            ext_data.extend(response.json()["assets"]["items"])
            # find the next page number (from the response)
            page_no = response.json()["assets"]["nextPage"]

            print(f"\r    {len(ext_data)} assets found so far...", end="", flush=True)

        print(f"\n  Done finding assets.\n")

    except requests.exceptions.RequestException as e:
        print(f"Error making API request to find external library assets: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        quit()

    return ext_data   # returns a list containing a dictionary for each asset

# Function that uploads an asset and returns the result of the upload (duplicate or new internal library item with asset id in either case)
def upload_asset(asset, ImportPath):
    data = {
        'deviceAssetId': asset['deviceAssetId'],
        'deviceId': 'Python Import',
        'fileCreatedAt': asset['fileCreatedAt'],
        'fileModifiedAt': asset['fileModifiedAt']
    }
    files = {
        'assetData': open(ImportPath, "rb")
    }

    try:
        response = requests.post(f"{IMMICH_URL}/api/assets", headers=headers2, data=data, files=files)
        response.raise_for_status()
        upload_result = response.json()
        return upload_result

    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return "error"

# Function to handle the case when the uploaded asset was detected as a duplicate
    # In this case the internal library asset gets added to all albums that the external library asset belonged to.
    # Returns a string confirming the action taken.
def handle_duplicate(asset, new_asset_id):
    # need to get the albums that the external asset was inside of
    params = {
        'assetId': asset['id'] # the ORIGINAL id of the external library asset
    }

    try:
        response = requests.get(f"{IMMICH_URL}/api/albums", headers=headers, params=params)
        response.raise_for_status()

        album_list = response.json() # list of dictionaries. The relevant key will be 'id', the album id for each list entry
        album_ids = []

        for album in album_list:
            album_ids.append(album["id"])

        # now add the new (internal) asset to each of the found albums
        payload = json.dumps({
            'assetIds': [new_asset_id], # must be an array
            'albumIds': album_ids
        })

        try:
            response = requests.put(f"{IMMICH_URL}/api/albums/assets", headers=headers, data=payload)
            response.raise_for_status()

            return "- albums merged."

        except requests.exceptions.RequestException as e:
            print(f"Error making API request: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return "error"

    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return "error"

# Function to copy metadata (including albums) from the external asset to the newly uploaded internal asset
def transfer_metadata(asset, new_asset_id):
    payload = json.dumps({
        'albums': True,
        'favorite': True,
        'sharedLinks': True,
        'sidecar': True,
        'stack': True,
        'sourceId': asset['id'],
        'targetId': new_asset_id
    })

    try:
        response = requests.put(f"{IMMICH_URL}/api/assets/copy", headers=headers, data=payload)
        response.raise_for_status()

        return "- metadata transferred."

    except requests.exceptions.RequestException as e:
        # print(f"Error encountered. Partial result for asset: {Result_Message}")
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return "error"

# Function to delete the asset (called after it is  fully copied to the internal library)
def delete_asset(asset):
    payload = {"ids": [asset['id']], 'force': DELETE_FROM_TRASH}

    try:
        response = requests.delete(f"{IMMICH_URL}/api/assets/", headers=headers, json=payload)
        response.raise_for_status()

        return "External asset deleted."

    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return "error"

# Start actions
print("""----- Immich Asset Mover -----
Script to transfer external library assets to the internal library, keeping metadata and albums intact.""")
# Show list of external libraries
get_libraries()
library_size = get_library_size()

# get list of assets to process
assets_list = get_assets_list()
asset_count = len(assets_list)
print(f"Processing {asset_count} assets from external library {LIBRARY_ID} ({library_size} mb).""")

# process assets
Current_Asset_No = 0
duplicates_count = 0
new_count = 0
processed_mb = 0
current_mb = 0
start_time = datetime.datetime.now()
assets_with_errors = []
error_count = 0
for asset in assets_list:
    Current_Asset_No += 1
    FileName = asset['originalPath'].replace(CONTAINER_PATH_PRE,"",1)
    ImportPath = asset['originalPath'].replace(CONTAINER_PATH_PRE, SYSTEM_PATH_PRE, 1)
    processed_mb += current_mb
    current_mb = round(os.path.getsize(ImportPath)/(1024*1024), 2)
    end_time = datetime.datetime.now()
    time_delta = str(end_time - start_time).split(".")[0]

    print(f" [{round(processed_mb / library_size * 100,3)}%, Dups={duplicates_count}, New={new_count}, errs={error_count}, time={time_delta}] File {Current_Asset_No} of {asset_count}: {FileName} ({current_mb} mb)", end=" ")

    # Attempt to upload the asset
    upload_result = upload_asset(asset, ImportPath)
    new_asset_id = upload_result["id"]
    new_asset_ids = [new_asset_id] # must be array
    if upload_result != "error":
        print(f"Upload result: {upload_result['status']}", end=" ")
    else:
        quit()
    if upload_result['status'] == 'duplicate':
        action_result=handle_duplicate(asset,new_asset_id)
        duplicates_count +=1
    else:
        action_result=transfer_metadata(asset,new_asset_id)
        new_count += 1

    print(f"{action_result}", end=" ")

    # now delete the original external library asset
    if action_result == "error":
        print("The original asset was not deleted because an error occurred.")
        assets_with_errors.append(asset['id'])
        error_count +=1
    else:
        delete_result = delete_asset(asset)
        print(f"{delete_result}")

print(f"""
---- COMPLETE ----
Uploaded assets: {asset_count}
Duplicates count: {duplicates_count}
New assets count: {new_count}

{error_count} errors occurred. The following assets were not deleted:
{assets_with_errors}
""")
