#!/usr/bin/env bash

# Prompt user for software name and port
read -rp "Enter the software name (used in the location path): " software
read -rp "Enter the port number the software is running on: " port

if [[ -f ~/.nginx/pid ]]; then
    echo "Installing proxypass for Nginx..."

    config_file="$HOME/.nginx/conf.d/000-default-server.d/$software.conf"

    if [[ -f "$config_file" ]]; then
        echo "Removing existing config for $software..."
        rm "$config_file"
        /usr/sbin/nginx -s reload -c ~/.nginx/nginx.conf > /dev/null 2>&1
    fi

    echo "Creating new proxy config for $software..."
    cat <<EOF > "$config_file"
location /$software {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Host $http_x_host;
    proxy_set_header X-NginX-Proxy true;


    rewrite /(.*) /$(whoami)/\$1 break;
    proxy_pass http://10.0.0.1:$port/;
    proxy_redirect off;
}
EOF

    /usr/sbin/nginx -s reload -c ~/.nginx/nginx.conf > /dev/null 2>&1
    echo "Proxy config for $software installed successfully."
else
    echo "Nginx doesn't appear to be running correctly..."
    echo
fi
