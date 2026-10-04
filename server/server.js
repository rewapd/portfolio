const express = require('express');
const cors = require('cors');
const profile = require('../client/public/profile.json');

const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json());

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'portfolio-api' });
});

app.get('/api/profile', (req, res) => {
  res.json(profile);
});

app.listen(PORT, () => {
  console.log(`Portfolio API running on http://localhost:${PORT}`);
});
