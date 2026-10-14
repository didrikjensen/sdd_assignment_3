db = db.getSiblingDB('sdd');
db.createUser({
  user: 'sdd',
  pwd: 'sdd',
  roles: [{ role: 'readWrite', db: 'sdd' }]
});
