#=========================================================================#
# Django + Gunicorn Socket Template for HestiaCP
#=========================================================================#

server {
    listen      %ip%:%proxy_port%;
    server_name %domain_idn% %alias_idn%;

    root        %docroot%;
    index       index.html;

    access_log  /var/log/%web_system%/domains/%domain%.log combined;
    access_log  /var/log/%web_system%/domains/%domain%.bytes bytes;
    error_log   /var/log/%web_system%/domains/%domain%.error.log error;

    location ~ /\.(?!well-known\/) {
        deny all;
        return 404;
    }

    location / {
        proxy_pass http://unix:/home/%user%/web/%domain%/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }

    location ~* ^.+\.(%proxy_extensions%)$ {
        try_files $uri @fallback;
        root %sdocroot%;
        expires max;
    }

    location @fallback {
        proxy_pass http://unix:/home/%user%/web/%domain%/gunicorn.sock;
    }

    location /static/ {
        alias %docroot%/static/;
        expires 30d;
    }

    location /media/ {
        alias %docroot%/media/;
        expires 30d;
    }

    include %home%/%user%/conf/web/%domain%/nginx.conf_*;
}