FROM nginx:alpine

# nginx serves the HTML/CSS/JS and forwards /api and /uploads to the backend container
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY *.html /usr/share/nginx/html/
COPY css /usr/share/nginx/html/css
COPY js /usr/share/nginx/html/js

EXPOSE 80
