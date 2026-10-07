FROM node:20-alpine
WORKDIR /app
ARG BACKEND_API_URL
ENV BACKEND_API_URL=${BACKEND_API_URL}
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000"]
