

# Export environment variables from .env file, handling quoted values and special characters
ENV_FILE="../../../.env"
if [ -f "$ENV_FILE" ]; then
	while IFS= read -r line; do
		# Skip comments and empty lines
		if [[ "$line" =~ ^# ]] || [[ -z "$line" ]]; then
			continue
		fi
		# Export the variable, preserving quotes and special characters
		eval export "$line"
	done < "$ENV_FILE"
else
	echo ".env file not found at $ENV_FILE"
fi
