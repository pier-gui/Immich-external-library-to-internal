# Immich External Library to Internal

## What?
This script automates the process of transferring external library assets to the internal immich library.
## Why?
Immich is now stable and a solid option to handle mobile device backup, rather than needing to use some other system for backups and giving immich access as an external library. Using its internal library allows for duplicate detection.
It is possible to simply upload your external library assets into immich directly, but there are a few problems with that approach.
- Need enough free disk space to hold all of the assets twice
- Because the uploaded assets will be detected as new, album information will not be carried over on import
## How does the script work?
1. Identify all assets within the external library
2. Upload the first asset (creates a new asset in the internal library)
   * If the asset was not detected as a duplicate, the metadata of the external library asset is copied to the (new) internal asset. This includes albums, favourite status, any manual changes to time/location, etc.
   Database processes/files (machine learning, thumbnails, etc.) will be re-generated for the new asset.
   * If the asset was detected as a duplicate (i.e. the same file was already in the internal library), immich will not upload it. It is possible that both versions of the asset (internal and external) belonged to different albums, so the script will add the existing internal asset to all albums that the external asset was part of.
4. Delete the external library asset
5. Repeate for all assets in the external library
## Prerequesites
 - Have a recent backup of your assets and database
 - API key from immich (under Account Settings - API Keys). You can examine the code to figure out which permissions are needed, or just allow all like I did.
 - Immich ID for the library (the script provides a list of all libraries to help with this)
 - Immich must have read/write permission for the external library (to delete assets)
 - Set the Configuration values at the top of the .py file before running it.
## Use at your own risk
I cobbled this together having no prior experience with http requests or Python. It ran fine on my setup but... have a backup plan ready in case something goes wrong.
