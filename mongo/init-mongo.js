const dbName = process.env.MONGO_INITDB_DATABASE || "medical";

const appUser = process.env.MONGO_APP_USER || "app_ingest";
const appPwd  = process.env.MONGO_APP_PASSWORD || "app_pwd";

const roUser  = process.env.MONGO_READONLY_USER || "app_readonly";
const roPwd   = process.env.MONGO_READONLY_PASSWORD || "ro_pwd";

db = db.getSiblingDB(dbName);

db.createUser({
    user: appUser,
    pwd: appPwd,
    roles: [{ role: "readWrite", db: dbName }]
});

db.createUser({
    user: roUser,
    pwd: roPwd,
    roles: [{ role: "read", db: dbName }]
});
