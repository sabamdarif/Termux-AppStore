#!/bin/bash
set -e

set -x

CHANGES_MADE=false

rm -f updated_apps.txt

echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la

if [ ! -d "apps" ]; then
	echo "Error: 'apps' directory not found!"
	exit 1
fi

update_version() {
	local file="$1"
	local old_version="$2"
	local new_version="$3"

	echo "File content before update:"
	cat "$file"

	sed -i "s/version=\"$old_version\"/version=\"$new_version\"/" "$file"

	echo "File content after update:"
	cat "$file"
}

for app_folder in apps/*; do
	app_name=$(basename "$app_folder")
	echo "Processing $app_name..."

	install_file="$app_folder/install.sh"

	[[ ! -d "$app_folder" || ! -f "$install_file" ]] && continue
	grep -q "version=.*local_version" "$install_file" && continue

	if grep -q "pause_update=true" "$install_file"; then
		echo "Skipping update check for $app_name (pause_update=true set)"
		continue
	fi

	page_url=$(grep 'page_url=' "$install_file" | cut -d '"' -f2)
	[[ -z "$page_url" || ! "$page_url" =~ github.com ]] && continue

	repo_name=$(echo "$page_url" | sed -E 's|https://github.com/([^/]+)/([^/]+)|\1/\2|')
	echo "Checking updates for $app_name (GitHub repo: $repo_name)"

	LATEST_VERSION=$(curl -s "https://api.github.com/repos/$repo_name/releases/latest" |
		grep '"tag_name":' |
		sed -E 's/.*"tag_name": "([^"]+)".*/\1/')

	[[ -z "$LATEST_VERSION" ]] && continue
	echo "Latest version for $app_name: $LATEST_VERSION"

	CURRENT_VERSION=$(grep '^version=' "$install_file" | head -n1 | cut -d '"' -f2)
	echo "Current version: $CURRENT_VERSION"

	if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
		echo "Updating $app_name from $CURRENT_VERSION to $LATEST_VERSION"

		update_version "$install_file" "$CURRENT_VERSION" "$LATEST_VERSION"

		NEW_VERSION=$(grep '^version=' "$install_file" | head -n1 | cut -d '"' -f2)
		if [[ "$NEW_VERSION" == "$LATEST_VERSION" ]]; then
			echo "Successfully updated version for $app_name"
			echo "- ${app_name}: ${CURRENT_VERSION} -> ${LATEST_VERSION}" >>updated_apps.txt
			CHANGES_MADE=true
		else
			echo "Failed to update version for $app_name"
		fi
	fi
done

if [ "$CHANGES_MADE" = true ]; then
	echo "Changes were made to some app versions"
	git status
else
	echo "No version changes were needed"
fi
