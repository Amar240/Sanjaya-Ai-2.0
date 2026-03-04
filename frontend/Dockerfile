FROM node:20-alpine AS build

WORKDIR /app/frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime

WORKDIR /app/frontend
ENV NODE_ENV=production

COPY --from=build /app/frontend ./

CMD ["npm", "run", "start", "--", "-p", "3000"]
