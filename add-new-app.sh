#!/bin/bash
#
# add-new-app.sh — scaffold a new Termux-AppStore app.
#
# Rewritten for Part D of the stability refactor (docs/REFACTOR_PLAN.md):
#   - Every field validates and re-prompts on bad input.
#   - Every field remembers its last-used value (bare Enter reuses it).
#   - Generated scripts use the high-level helpers in inbuild_functions
#     (create_desktop_entry / detect_arch / install_* / standard_uninstall) so
#     they stay short, and no longer hand-write [Desktop Entry] heredocs.
#   - Every download prompts for a pinned SHA256 (or the literal `skip`) and
#     emits the runtime-only `sha256` header (Part C-bis).
#
# Metadata still lives in install.sh (decision): the parser in
# .github/scripts/update_metadata.py reads supported_arch=/package_name=/
# run_cmd=/version=/app_type=/supported_distro= from the top of the file, so
# those assignments are always emitted near the top, one per line.

set -uo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES=(
	"Accessories"
	"Development"
	"Games"
	"Graphics"
	"Internet"
	"Multimedia"
	"Office"
	"Productivity"
)

# Where per-field "last used" answers are persisted between runs. Kept in the
# repo root and gitignored (see D1).
DEFAULTS_FILE=".add-new-app.defaults"

# In-memory store of defaults, loaded from DEFAULTS_FILE at startup.
declare -A DEFAULTS=()

# PID of the top-level shell, used to abort from inside $() subshells (where a
# plain `exit` would only leave the subshell).
MAIN_PID=$$

# Abort the whole program with a message. Works from inside command
# substitution because it signals the top-level shell, not just this subshell.
abort() {
	echo "add-new-app: ${1:-aborted}" >&2
	kill "$MAIN_PID" 2>/dev/null
	exit 1
}

# read_line <var> <prompt>  -> read one line into <var>, aborting on EOF
# (Ctrl+D / exhausted stdin) instead of looping forever on a required prompt.
# The prompt goes to stderr so it survives command substitution.
read_line() {
	local __var="$1" __prompt="$2" __line
	if ! IFS= read -r -p "$__prompt" __line; then
		# read failed: EOF. A non-empty buffer is a valid final line with no
		# trailing newline; a truly empty buffer means no more input.
		[ -z "$__line" ] && abort "unexpected end of input"
	fi
	printf -v "$__var" '%s' "$__line"
}

# ---------------------------------------------------------------------------
# Defaults persistence (D1)
# ---------------------------------------------------------------------------

load_defaults() {
	[ -f "$DEFAULTS_FILE" ] || return 0
	local key val line
	while IFS= read -r line; do
		# lines look like: key=value   (value may contain '=')
		[[ "$line" == *"="* ]] || continue
		key="${line%%=*}"
		val="${line#*=}"
		[ -n "$key" ] && DEFAULTS["$key"]="$val"
	done <"$DEFAULTS_FILE"
}

# Built-in first-run defaults for fields the user hasn't answered before.
builtin_default() {
	case "$1" in
	supported_archs) echo "aarch64" ;;
	app_type) echo "native" ;;
	supported_distro) echo "all" ;;
	mechanism) echo "native" ;;
	*) echo "" ;;
	esac
}

# Get the current default for a field: last-used value if present, else the
# built-in default.
default_for() {
	local key="$1"
	if [ -n "${DEFAULTS[$key]+x}" ] && [ -n "${DEFAULTS[$key]}" ]; then
		echo "${DEFAULTS[$key]}"
	else
		builtin_default "$key"
	fi
}

# Remember a field's value in memory (persisted to disk at the end of main()).
remember() {
	local key="$1" val="$2"
	DEFAULTS["$key"]="$val"
}

save_defaults() {
	local key
	: >"$DEFAULTS_FILE"
	for key in "${!DEFAULTS[@]}"; do
		printf '%s=%s\n' "$key" "${DEFAULTS[$key]}" >>"$DEFAULTS_FILE"
	done
}

# ---------------------------------------------------------------------------
# Generic prompts (all show [default: ...] and reuse on bare Enter)
# ---------------------------------------------------------------------------

# prompt_field <key> <prompt-text> [allow_empty]  -> prints the answer.
# Bare Enter reuses the stored default. Empty answers are only accepted when
# there is no default to fall back on AND the caller allows it. The caller is
# responsible for calling remember() on the result (these run in $() subshells,
# so they cannot update the parent's DEFAULTS themselves).
prompt_field() {
	local key="$1" text="$2" allow_empty="${3:-no}"
	local def answer
	def="$(default_for "$key")"

	while true; do
		if [ -n "$def" ]; then
			read_line answer "$text [default: $def]: "
		else
			read_line answer "$text: "
		fi
		# Bare Enter reuses default.
		[ -z "$answer" ] && answer="$def"

		if [ -z "$answer" ] && [ "$allow_empty" != "yes" ]; then
			echo "  This field is required." >&2
			continue
		fi
		echo "$answer"
		return 0
	done
}

# prompt_choice <key> <prompt-text> <valid...>  -> one of the valid options.
prompt_choice() {
	local key="$1" text="$2"
	shift 2
	local valid=("$@")
	local def answer opt
	def="$(default_for "$key")"

	while true; do
		read_line answer "$text (${valid[*]}) [default: $def]: "
		answer="$(echo "$answer" | tr -d '[:space:]')"
		[ -z "$answer" ] && answer="$def"
		for opt in "${valid[@]}"; do
			if [ "$answer" = "$opt" ]; then
				echo "$answer"
				return 0
			fi
		done
		echo "  Invalid choice. Choose from: ${valid[*]}" >&2
	done
}

# prompt_multi <key> <prompt-text> <valid...>  -> validated CSV (comma-joined).
# Every token must be one of the valid options.
prompt_multi() {
	local key="$1" text="$2"
	shift 2
	local valid=("$@")
	local def answer tok opt ok
	def="$(default_for "$key")"

	while true; do
		read_line answer "$text (comma-separated: ${valid[*]}) [default: $def]: "
		[ -z "$answer" ] && answer="$def"

		local -a selected=()
		local all_valid=true
		IFS=',' read -ra selected <<<"$answer"
		if [ "${#selected[@]}" -eq 0 ]; then
			echo "  Select at least one." >&2
			continue
		fi
		for tok in "${selected[@]}"; do
			tok="$(echo "$tok" | tr -d '[:space:]')"
			ok=false
			for opt in "${valid[@]}"; do
				[ "$tok" = "$opt" ] && ok=true && break
			done
			if [ "$ok" = false ]; then
				all_valid=false
				break
			fi
		done
		if [ "$all_valid" = true ]; then
			# normalize to trimmed, comma-joined
			local out=""
			for tok in "${selected[@]}"; do
				tok="$(echo "$tok" | tr -d '[:space:]')"
				out="${out:+$out,}$tok"
			done
			echo "$out"
			return 0
		fi
		echo "  Invalid choice(s). Choose from: ${valid[*]}" >&2
	done
}

# prompt_yesno <key> <prompt-text>  -> "yes" or "no".
prompt_yesno() {
	local key="$1" text="$2"
	local def answer
	def="$(default_for "$key")"
	[ -z "$def" ] && def="no"

	while true; do
		read_line answer "$text (yes/no) [default: $def]: "
		answer="$(echo "$answer" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
		[ -z "$answer" ] && answer="$def"
		case "$answer" in
		y | yes)
			echo "yes"
			return 0
			;;
		n | no)
			echo "no"
			return 0
			;;
		esac
		echo "  Please answer yes or no." >&2
	done
}

# ---------------------------------------------------------------------------
# Field-specific validators
# ---------------------------------------------------------------------------

sanitize_folder_name() {
	local name="$1"
	# lowercase everything, then capitalize the first character, spaces -> hyphens
	name=$(echo "$name" | tr '[:upper:]' '[:lower:]' | sed 's/^ *\(.\)/\U\1/')
	echo "${name// /-}"
}

# prompt_url <key> <prompt-text>  -> a syntactically valid http(s) URL.
prompt_url() {
	local key="$1" text="$2"
	local answer
	while true; do
		answer="$(prompt_field "$key" "$text")"
		if [[ "$answer" =~ ^https?://[^[:space:]]+$ ]]; then
			echo "$answer"
			return 0
		fi
		echo "  Enter a valid http(s):// URL." >&2
	done
}

# detect_version_from_url <url>  -> prints the release tag if the URL looks like
# a GitHub release-download URL, else prints nothing.
detect_version_from_url() {
	local url="$1"
	if [[ "$url" =~ /releases/download/([^/]+)/ ]]; then
		echo "${BASH_REMATCH[1]}"
	fi
}

# prompt_version <detected>  -> a non-empty version string, defaulting to the
# detected tag when available.
prompt_version() {
	local detected="$1"
	if [ -n "$detected" ]; then
		DEFAULTS["version"]="$detected"
	fi
	prompt_field "version" "Enter version (tag)"
}

# prompt_sha256 <key> <label>  -> a 64-hex checksum or the literal "skip".
# Emitting the checksum is required for reproducible/secure downloads (CB1/CB4);
# `skip` is the explicit opt-out for genuinely unpinnable URLs.
prompt_sha256() {
	local key="$1" label="$2"
	local answer
	while true; do
		answer="$(prompt_field "$key" "Enter SHA256 for $label (64 hex chars, or 'skip')")"
		answer="$(echo "$answer" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
		if [ "$answer" = "skip" ]; then
			echo "skip"
			return 0
		fi
		if [[ "$answer" =~ ^[0-9a-f]{64}$ ]]; then
			echo "$answer"
			return 0
		fi
		echo "  Must be exactly 64 hex characters, or the literal 'skip'." >&2
	done
}

# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------
#
# All generators share this convention:
#   * metadata assignments come first, one per line (parser-friendly);
#   * the sha256 header (if any) comes right after metadata;
#   * the body uses the high-level helpers and never calls progress_phase /
#     progress_done (the runner brackets the script via __appstore_begin/end).

TERMUX_SHEBANG="#!/data/data/com.termux/files/usr/bin/bash"

# arch_to_archtype <arch>  -> the release-artifact token detect_arch maps it to.
# Must stay in sync with the `detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf`
# call the generators emit, so map keys match the filenames downloaded at runtime.
arch_to_archtype() {
	case "$1" in
	aarch64) echo "arm64" ;;
	armv7*) echo "armv7l" ;;
	arm) echo "armhf" ;;
	*) echo "$1" ;;
	esac
}

# build_sha_header <filename-template> <archs-csv>  -> prints the runtime-only
# `sha256` header block for an app that downloads artifacts (CB1). Prompts on
# stderr; only the header text goes to stdout (safe inside $()).
#
#   * single artifact (one arch, or a template with no ${archtype})  -> scalar
#       sha256="<hex>"                (or sha256="skip")
#   * arch-specific artifacts (>1 arch AND ${archtype} in the name)  -> a map
#       declare -A sha256=( ["name_arm64.deb"]="<hex>" ["name_armhf.deb"]="…" )
#     keyed by the archtype-substituted filename so download_file's per-file
#     lookup (CB2) matches the concrete download on each device.
build_sha_header() {
	local filename_tmpl="$1" archs_csv="$2"
	local -a arch_list=()
	IFS=',' read -ra arch_list <<<"$archs_csv"

	# Single artifact: emit a scalar. The literal ${archtype} test is intentional
	# (we check whether the template still contains the placeholder), so the
	# single-quotes are deliberate here.
	# shellcheck disable=SC2016
	if [ "${#arch_list[@]}" -le 1 ] || [[ "$filename_tmpl" != *'${archtype}'* ]]; then
		local sha
		sha="$(prompt_sha256 "sha256" "$filename_tmpl")"
		printf 'sha256="%s"\n' "$sha"
		return 0
	fi

	# Arch-specific artifacts: prompt per arch, keyed by concrete filename.
	local arch archtype key sha lines="" all_skip=1
	for arch in "${arch_list[@]}"; do
		archtype="$(arch_to_archtype "$arch")"
		key="${filename_tmpl//\$\{archtype\}/$archtype}"
		sha="$(prompt_sha256 "sha256_$archtype" "$key")"
		[ "$sha" != "skip" ] && all_skip=0
		lines="${lines}    [\"${key}\"]=\"${sha}\""$'\n'
	done

	# If the contributor skipped every arch, collapse to a single scalar opt-out.
	if [ "$all_skip" -eq 1 ]; then
		printf 'sha256="skip"\n'
		return 0
	fi
	printf 'declare -A sha256=(\n%s)\n' "$lines"
}

# --- native package -------------------------------------------------------
gen_native() {
	local path="$1" archs="$2" pkg="$3" run_cmd="$4" version="$5"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "supported_arch=\"$archs\""
		echo "package_name=\"$pkg\""
		echo "run_cmd=\"$run_cmd\""
		echo "version=\"$version\""
		echo "app_type=\"native\""
		echo
		echo "package_install_and_check \"\$package_name\""
	} >"$path"
}

# --- multi-package (native, several packages) -----------------------------
# Native app that installs several packages in one shot. `package_name` stays a
# single primary name (detection greps `^ii <package_name>` and resolves the
# version from it); the full space-separated install list is passed to
# package_install_and_check, which splits on spaces and handles wildcards +
# retries. The `packages` file (written by main) is an informational
# alternatives list (`a | b`) for humans — nothing parses it at runtime today.
gen_multi_package() {
	local path="$1" archs="$2" pkg="$3" run_cmd="$4" version="$5" install_list="$6"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "supported_arch=\"$archs\""
		echo "package_name=\"$pkg\""
		echo "run_cmd=\"$run_cmd\""
		echo "version=\"$version\""
		echo "app_type=\"native\""
		echo
		echo "# Primary detection/version package is \$package_name; the full set"
		echo "# installed in one shot is listed below (space-separated)."
		echo "package_install_and_check \"$install_list\""
	} >"$path"
}

# --- native .deb (works on apt + pacman Termux) ---------------------------
gen_native_deb() {
	local path="$1" archs="$2" pkg="$3" run_cmd="$4" version="$5"
	local base_url="$6" filename_tmpl="$7" sha_header="$8"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "supported_arch=\"$archs\""
		echo "package_name=\"$pkg\""
		echo "run_cmd=\"$run_cmd\""
		echo "version=\"$version\""
		echo "app_type=\"native\""
		echo "$sha_header"
		echo "page_url=\"$base_url\""
		echo
		echo "archtype=\$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)"
		echo "install_deb_into_termux \\"
		echo "    \"\${page_url}/releases/download/\${version}/${filename_tmpl}\""
	} >"$path"
}

# --- AppImage --------------------------------------------------------------
gen_appimage() {
	local path="$1" archs="$2" pkg="$3" run_cmd="$4" version="$5"
	local base_url="$6" filename_tmpl="$7" sha_header="$8"
	local folder="$9" categories="${10}" name="${11:-${pkg^}}"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "supported_arch=\"$archs\""
		echo "package_name=\"$pkg\""
		echo "run_cmd=\"$run_cmd\""
		echo "version=\"$version\""
		echo "app_type=\"distro\""
		echo "supported_distro=\"all\""
		echo "$sha_header"
		echo "page_url=\"$base_url\""
		echo
		echo "archtype=\$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)"
		echo "appimage_filename=\"${filename_tmpl}\""
		echo "download_file \"\${page_url}/releases/download/\${version}/\${appimage_filename}\""
		echo "install_appimage \"\$appimage_filename\" \"$pkg\""
		echo "create_desktop_entry \\"
		echo "    --name \"${name}\" --pkg \"$pkg\" \\"
		echo "    --exec \"$run_cmd\" \\"
		echo "    --wmclass \"$pkg\" --comment \"$pkg\" \\"
		echo "    --categories \"${categories}\" \\"
		echo "    --logo-dir \"$folder\""
	} >"$path"
}

# --- .deb / .rpm -> distro -------------------------------------------------
gen_deb_into_distro() {
	local path="$1" archs="$2" pkg="$3" run_cmd="$4" version="$5"
	local base_url="$6" filename_tmpl="$7" sha_header="$8"
	local folder="$9" categories="${10}" name="${11:-${pkg^}}"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "supported_arch=\"$archs\""
		echo "package_name=\"$pkg\""
		echo "run_cmd=\"$run_cmd\""
		echo "version=\"$version\""
		echo "app_type=\"distro\""
		echo "supported_distro=\"all\""
		echo "$sha_header"
		echo "page_url=\"$base_url\""
		echo
		echo "archtype=\$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)"
		echo "filename=\"${filename_tmpl}\""
		echo "install_deb_into_distro \\"
		echo "    \"\${page_url}/releases/download/\${version}/\${filename}\" \\"
		echo "    \"\${filename}\""
		echo "create_desktop_entry \\"
		echo "    --name \"${name}\" --pkg \"$pkg\" \\"
		echo "    --exec \"$run_cmd\" \\"
		echo "    --wmclass \"$pkg\" --comment \"$pkg\" \\"
		echo "    --categories \"${categories}\" \\"
		echo "    --logo-dir \"$folder\""
	} >"$path"
}

# --- tar/zip -> /opt in distro --------------------------------------------
gen_archive_into_opt() {
	local path="$1" archs="$2" pkg="$3" run_cmd="$4" version="$5"
	local base_url="$6" filename_tmpl="$7" sha_header="$8"
	local folder="$9" categories="${10}" name="${11:-${pkg^}}"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "supported_arch=\"$archs\""
		echo "package_name=\"$pkg\""
		echo "run_cmd=\"$run_cmd\""
		echo "version=\"$version\""
		echo "app_type=\"distro\""
		echo "supported_distro=\"all\""
		echo "$sha_header"
		echo "page_url=\"$base_url\""
		echo
		echo "archtype=\$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)"
		echo "install_archive_into_opt \"$pkg\" \\"
		echo "    \"\${page_url}/releases/download/\${version}/${filename_tmpl}\""
		echo "create_desktop_entry \\"
		echo "    --name \"${name}\" --pkg \"$pkg\" \\"
		echo "    --exec \"$run_cmd\" \\"
		echo "    --wmclass \"$pkg\" --comment \"$pkg\" \\"
		echo "    --categories \"${categories}\" \\"
		echo "    --logo-dir \"$folder\""
	} >"$path"
}

# --- distro-repo package (GPG key + repo file) — scaffolded TODO stub ------
gen_distro_repo() {
	local path="$1" archs="$2" pkg="$3" run_cmd="$4" version="$5"
	local supported_distro="$6" folder="$7" categories="${8}" name="${9:-${pkg^}}"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "supported_arch=\"$archs\""
		echo "package_name=\"$pkg\""
		echo "run_cmd=\"$run_cmd\""
		echo "version=\"$version\""
		echo "app_type=\"distro\""
		echo "supported_distro=\"$supported_distro\""
		echo
		echo "# TODO(contributor): this app installs from a custom distro repository."
		echo "# Set up the GPG key + repo file for each supported distro below, then"
		echo "# install with pd_package_install_and_check. See apps/Cursor or apps/Code"
		echo "# for complete, working examples of the key/repo dance."
		echo "case \"\$SELECTED_DISTRO\" in"
		echo "debian | ubuntu)"
		echo "    # TODO: add apt key + /etc/apt/sources.list.d/<repo>.list, then:"
		echo "    pd_package_install_and_check \"$pkg\""
		echo "    ;;"
		echo "fedora)"
		echo "    # TODO: add dnf repo under /etc/yum.repos.d/, then:"
		echo "    pd_package_install_and_check \"$pkg\""
		echo "    ;;"
		echo "arch | archlinux)"
		echo "    pd_package_install_and_check \"$pkg\""
		echo "    ;;"
		echo "*)"
		echo "    print_failed \"Unsupported distribution: \$SELECTED_DISTRO\""
		echo "    ;;"
		echo "esac"
		echo
		echo "create_desktop_entry \\"
		echo "    --name \"${name}\" --pkg \"$pkg\" \\"
		echo "    --exec \"$run_cmd\" \\"
		echo "    --wmclass \"$pkg\" --comment \"$pkg\" \\"
		echo "    --categories \"${categories}\" \\"
		echo "    --logo-dir \"$folder\""
	} >"$path"
}

# ---------------------------------------------------------------------------
# Uninstall generation — one-liners via standard_uninstall (C6). D4 fix: the
# old TERMUX_PREFIXFIX typo and hand-written removals are gone.
# ---------------------------------------------------------------------------

gen_uninstall() {
	local path="$1" mechanism="$2" pkg="$3"
	{
		echo "$TERMUX_SHEBANG"
		echo
		echo "app_type=\"$(app_type_for_mechanism "$mechanism")\""
		echo
		case "$mechanism" in
		native | native_deb | multi_package)
			echo "standard_uninstall --native \"$pkg\""
			;;
		distro_repo | deb_into_distro)
			echo "standard_uninstall --distro \"$pkg\""
			;;
		appimage)
			echo "standard_uninstall --opt \"/opt/AppImageLauncher/$pkg\" --desktop \"$pkg\""
			;;
		archive_into_opt)
			echo "standard_uninstall --opt \"/opt/$pkg\" --desktop \"$pkg\""
			;;
		*)
			echo "standard_uninstall \"$pkg\""
			;;
		esac
	} >"$path"
}

app_type_for_mechanism() {
	case "$1" in
	native | native_deb | multi_package) echo "native" ;;
	*) echo "distro" ;;
	esac
}

# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

main() {
	load_defaults

	echo "=== Add a new Termux-AppStore app ==="
	echo "(bare Enter reuses the [default] shown for each field)"
	echo

	# --- app name / folder ---
	local app_name folder_name app_dir
	while true; do
		app_name="$(prompt_field "app_name" "Enter app name")"
		folder_name="$(sanitize_folder_name "$app_name")"
		app_dir="apps/$folder_name"
		if [ -d "$app_dir" ]; then
			local ow
			ow="$(prompt_yesno "overwrite" "apps/$folder_name already exists. Overwrite?")"
			if [ "$ow" = "yes" ]; then
				break
			fi
			# else: loop and ask for a different name
		else
			break
		fi
	done
	remember "app_name" "$app_name"

	# --- architectures ---
	local supported_archs
	supported_archs="$(prompt_multi "supported_archs" "Supported architectures" "aarch64" "arm")"
	remember "supported_archs" "$supported_archs"

	# --- mechanism ---
	echo
	echo "Install mechanisms:"
	echo "  native            - Termux package (package_install_and_check)"
	echo "  multi_package     - native, several packages via a 'packages' file"
	echo "  native_deb        - .deb installed into Termux (apt + pacman)"
	echo "  appimage          - AppImage installed via the distro"
	echo "  deb_into_distro   - .deb/.rpm installed inside the distro"
	echo "  archive_into_opt  - tar/zip extracted into /opt in the distro"
	echo "  distro_repo       - distro package from a custom repo (scaffold stub)"
	local mechanism
	mechanism="$(prompt_choice "mechanism" "Choose mechanism" \
		native multi_package native_deb appimage deb_into_distro archive_into_opt distro_repo)"
	remember "mechanism" "$mechanism"

	# app_type is derived from the mechanism.
	local app_type
	app_type="$(app_type_for_mechanism "$mechanism")"

	# --- distro selection (only for distro_repo, where repo differs per distro) ---
	local supported_distro="all"
	if [ "$mechanism" = "distro_repo" ]; then
		supported_distro="$(prompt_choice "supported_distro" "Supported distro" \
			debian ubuntu fedora all)"
		remember "supported_distro" "$supported_distro"
	fi

	# --- package name ---
	local package_name
	package_name="$(prompt_field "package_name" "Enter package name")"
	remember "package_name" "$package_name"

	# --- download URL / version / sha / filename template (download mechanisms) ---
	local download_url="" base_url="" version="" filename_tmpl="" sha_header=""
	case "$mechanism" in
	native_deb | appimage | deb_into_distro | archive_into_opt)
		download_url="$(prompt_url "download_url" "Enter a sample download URL for one artifact")"
		remember "download_url" "$download_url"
		base_url="${download_url%/releases/download/*}"

		local detected
		detected="$(detect_version_from_url "$download_url")"
		if [ -n "$detected" ]; then
			echo "  Detected version: $detected"
		fi
		version="$(prompt_version "$detected")"
		remember "version" "$version"

		# Turn the concrete sample URL's basename into a template using
		# ${version} / ${version#v} / ${archtype} — no sed over user input (D4).
		filename_tmpl="$(build_filename_template "$(basename "$download_url")" "$version" "$supported_archs")"
		echo "  Filename template: $filename_tmpl"

		# Runtime-only sha256 header: a scalar for a single artifact, or a
		# per-filename map for arch-specific downloads (CB1/D2).
		sha_header="$(build_sha_header "$filename_tmpl" "$supported_archs")"
		;;
	*)
		# non-downloading mechanisms: version defaults to the local marker
		if [ "$app_type" = "native" ]; then
			DEFAULTS["version"]="${DEFAULTS[version]:-termux_local_version}"
		else
			DEFAULTS["version"]="${DEFAULTS[version]:-distro_local_version}"
		fi
		version="$(prompt_field "version" "Enter version")"
		remember "version" "$version"
		;;
	esac

	# --- run command (never empty; sensible default per mechanism) ---
	# For mechanisms with a clear canonical Exec path (appimage, archive_into_opt)
	# the mechanism-derived default wins over any stale cross-mechanism value;
	# otherwise fall back to the stored value, then to the package name.
	local run_cmd_default
	run_cmd_default="$(default_run_cmd "$mechanism" "$package_name")"
	case "$mechanism" in
	appimage | archive_into_opt)
		DEFAULTS["run_cmd"]="$run_cmd_default"
		;;
	*)
		DEFAULTS["run_cmd"]="${DEFAULTS[run_cmd]:-$run_cmd_default}"
		;;
	esac
	local run_cmd
	run_cmd="$(prompt_field "run_cmd" "Enter run command")"
	remember "run_cmd" "$run_cmd"

	# --- description ---
	echo
	echo "Enter app description (end with a single '.' on its own line):"
	local description="" dline
	while IFS= read -r dline; do
		[ "$dline" = "." ] && break
		description="${description:+$description
}$dline"
	done

	# --- categories ---
	local -a selected_categories=()
	echo
	echo "Available categories:"
	local i
	for i in "${!CATEGORIES[@]}"; do
		echo "  $((i + 1)). ${CATEGORIES[i]}"
	done
	while true; do
		local choice
		read_line choice "Select category number (Enter when done): "
		[ -z "$choice" ] && break
		if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#CATEGORIES[@]}" ]; then
			local category="${CATEGORIES[$((choice - 1))]}"
			local exists=false existing
			for existing in "${selected_categories[@]}"; do
				[ "$existing" = "$category" ] && exists=true && break
			done
			if [ "$exists" = false ]; then
				selected_categories+=("$category")
				echo "  Added: $category"
			fi
		else
			echo "  Invalid category number."
		fi
	done
	if [ "${#selected_categories[@]}" -eq 0 ]; then
		echo "At least one category must be selected." >&2
		return 1
	fi
	# .desktop Categories= value (semicolon-terminated list)
	local desktop_categories=""
	local c
	for c in "${selected_categories[@]}"; do
		desktop_categories="${desktop_categories}${c};"
	done

	# --- create the app directory + metadata files ---
	rm -rf "$app_dir"
	mkdir -p "$app_dir"

	printf '%s\n' "$description" >"$app_dir/description.txt"
	(
		IFS=,
		echo "${selected_categories[*]}"
	) >"$app_dir/category.txt"

	# --- generate install + uninstall ---
	local install_sh="$app_dir/install.sh"
	local uninstall_sh="$app_dir/uninstall.sh"

	case "$mechanism" in
	native)
		gen_native "$install_sh" "$supported_archs" "$package_name" "$run_cmd" "$version"
		;;
	multi_package)
		# package_name stays a single name (used for install-state detection and
		# version resolution). The full space-separated install list is separate.
		DEFAULTS["install_list"]="${DEFAULTS[install_list]:-$package_name}"
		local install_list
		install_list="$(prompt_field "install_list" "Enter all packages to install (space-separated, '*' wildcards ok)")"
		remember "install_list" "$install_list"
		gen_multi_package "$install_sh" "$supported_archs" "$package_name" "$run_cmd" "$version" "$install_list"
		# The `packages` file records the alternatives list (one entry per line,
		# `a | b` for alternatives) for maintainers and future tooling.
		printf '%s\n' "$install_list" >"$app_dir/packages"
		echo "  Created apps/$folder_name/packages — edit to record package alternatives (one per line)."
		;;
	native_deb)
		gen_native_deb "$install_sh" "$supported_archs" "$package_name" "$run_cmd" "$version" \
			"$base_url" "$filename_tmpl" "$sha_header"
		;;
	appimage)
		gen_appimage "$install_sh" "$supported_archs" "$package_name" "$run_cmd" "$version" \
			"$base_url" "$filename_tmpl" "$sha_header" "$folder_name" "$desktop_categories" "$app_name"
		;;
	deb_into_distro)
		gen_deb_into_distro "$install_sh" "$supported_archs" "$package_name" "$run_cmd" "$version" \
			"$base_url" "$filename_tmpl" "$sha_header" "$folder_name" "$desktop_categories" "$app_name" "$app_name"
		;;
	archive_into_opt)
		gen_archive_into_opt "$install_sh" "$supported_archs" "$package_name" "$run_cmd" "$version" \
			"$base_url" "$filename_tmpl" "$sha_header" "$folder_name" "$desktop_categories" "$app_name" "$app_name"
		;;
	distro_repo)
		gen_distro_repo "$install_sh" "$supported_archs" "$package_name" "$run_cmd" "$version" \
			"$supported_distro" "$folder_name" "$desktop_categories" "$app_name" "$app_name"
		;;
	esac
	gen_uninstall "$uninstall_sh" "$mechanism" "$package_name"

	chmod 755 "$install_sh" "$uninstall_sh"

	# --- logo ---
	while true; do
		local logo_path
		read_line logo_path $'\nEnter path to logo (PNG or SVG): '
		logo_path="${logo_path//[\'\"]/}"
		if [ -f "$logo_path" ]; then
			if [[ "$logo_path" =~ \.png$ ]]; then
				cp "$logo_path" "$app_dir/logo.png"
				echo "  PNG logo copied."
				break
			elif [[ "$logo_path" =~ \.svg$ ]]; then
				cp "$logo_path" "$app_dir/logo.svg"
				echo "  SVG logo copied."
				break
			else
				echo "  Provide a PNG or SVG file."
			fi
		else
			echo "  No such file."
		fi
	done

	echo
	echo "App '$app_name' created in $app_dir"
	echo "Review the generated scripts:"
	echo "  $install_sh"
	echo "  $uninstall_sh"
	if [ "$mechanism" = "distro_repo" ]; then
		echo "NOTE: distro_repo is a scaffold — fill in the GPG key / repo setup TODOs."
	fi
	if [[ "$sha_header" == *'"skip"'* ]]; then
		echo "NOTE: SHA256 verification was skipped — pin a checksum before release if you can."
	fi

	# Persist this run's answers as next run's per-field defaults (D1).
	save_defaults
}

# default_run_cmd <mechanism> <pkg>  -> a sensible non-empty Exec target.
default_run_cmd() {
	local mechanism="$1" pkg="$2"
	case "$mechanism" in
	appimage) echo "/opt/AppImageLauncher/$pkg/$pkg --no-sandbox" ;;
	archive_into_opt) echo "/opt/$pkg/$pkg --no-sandbox" ;;
	*) echo "$pkg" ;;
	esac
}

# build_filename_template <basename> <version> <archs-csv> -> the basename with
# the concrete version/arch replaced by ${version} / ${version#v} / ${archtype}
# template variables, using bash parameter expansion (no sed over user input).
build_filename_template() {
	local name="$1" version="$2" archs="$3"
	local vnov="${version#v}"

	# Replace the version tag (with and without a leading v) first.
	if [ -n "$version" ]; then
		name="${name//$version/\$\{version\}}"
	fi
	if [ -n "$vnov" ] && [ "$vnov" != "$version" ]; then
		name="${name//$vnov/\$\{version#v\}}"
	fi

	# Replace concrete arch tokens with ${archtype}. Cover the common release
	# spellings mapped by detect_arch (arm64/armv7l/armhf/aarch64).
	local tok
	for tok in arm64 aarch64 armv7l armhf; do
		name="${name//$tok/\$\{archtype\}}"
	done

	echo "$name"
}

main "$@"
