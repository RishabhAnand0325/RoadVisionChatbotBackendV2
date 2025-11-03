# TenderIQ Date Filtering API - Quick Reference

**Status**: ✅ Production Ready | **Tests**: 25/25 Passing | **Base URL**: `/api/v1/tenderiq`

---

## 📅 Endpoint 1: Get Available Dates

### Request
```
GET /dates
```

### Response (200 OK)
```json
{
  "dates": [
    {
      "date": "2024-11-03",
      "date_str": "November 3, 2024",
      "run_at": "2024-11-03T10:30:00Z",
      "tender_count": 45,
      "is_latest": true
    },
    {
      "date": "2024-11-02",
      "date_str": "November 2, 2024",
      "run_at": "2024-11-02T09:15:00Z",
      "tender_count": 38,
      "is_latest": false
    }
  ]
}
```

### Use Case
Populate date selector dropdown in frontend

---

## 📋 Endpoint 2: Get Filtered Tenders

### Request
```
GET /tenders[?date=YYYY-MM-DD][?date_range=...][?include_all_dates=...][&category=...][&location=...]
```

### Query Parameters

| Parameter | Type | Optional | Default | Example |
|-----------|------|----------|---------|---------|
| `date` | string | Yes | - | `2024-11-03` |
| `date_range` | string | Yes | - | `last_5_days` |
| `include_all_dates` | boolean | Yes | `false` | `true` |
| `category` | string | Yes | - | `Civil` |
| `location` | string | Yes | - | `Mumbai` |
| `min_value` | number | Yes | - | `100` |
| `max_value` | number | Yes | - | `500` |

### Valid Date Ranges
- `last_1_day`
- `last_5_days`
- `last_7_days`
- `last_30_days`

### Response (200 OK)
```json
{
  "tenders": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "tender_id_str": "TEN-2024-001",
      "tender_name": "Construction of Multi-Story Building",
      "tender_url": "https://...",
      "city": "Mumbai",
      "value": "250 Crore",
      "due_date": "2024-11-15",
      "summary": "Building construction project in central Mumbai",
      "query_name": "Civil",
      "tender_type": "Open",
      "state": "Maharashtra",
      "publish_date": "2024-11-03",
      "last_date_of_bid_submission": "2024-11-15",
      "tender_value": "250 Crore"
    }
  ],
  "total_count": 12,
  "filtered_by": {
    "date_range": "last_5_days",
    "category": "Civil"
  },
  "available_dates": [
    "2024-11-03",
    "2024-11-02",
    "2024-11-01"
  ]
}
```

### Filter Priority
When multiple date filters are provided, they are applied in this priority:
1. **Highest**: `include_all_dates=true` → All historical tenders
2. **Medium**: `date=YYYY-MM-DD` → Specific date only
3. **Lowest**: `date_range=last_N_days` → Date range
4. **Default** (no params): `last_1_day`

### Request Examples

#### Example 1: Get tenders from last 5 days
```
GET /tenders?date_range=last_5_days
```

#### Example 2: Get Civil tenders from November 3
```
GET /tenders?date=2024-11-03&category=Civil
```

#### Example 3: Get all tenders from Mumbai, value 100-500 crore
```
GET /tenders?include_all_dates=true&location=Mumbai&min_value=100&max_value=500
```

#### Example 4: Complex filter (last 7 days, Electrical, Delhi)
```
GET /tenders?date_range=last_7_days&category=Electrical&location=Delhi
```

#### Example 5: Get latest tenders (default)
```
GET /tenders
```

---

## ⚠️ Error Responses

### 400 Bad Request - Invalid Date Format
```json
{
  "detail": "Invalid date format. Use YYYY-MM-DD"
}
```
**Fix**: Use exactly YYYY-MM-DD format (e.g., `2024-11-03`)

### 400 Bad Request - Invalid Date Range
```json
{
  "detail": "Invalid date_range: last_100_days. Must be one of: last_1_day, last_5_days, last_7_days, last_30_days"
}
```
**Fix**: Use one of the valid date ranges listed above

### 404 Not Found - No Data
```json
{
  "detail": "No scraped tenders found in the database."
}
```
**Fix**: Run the scraper first to populate data

### 500 Internal Server Error
```json
{
  "detail": "Failed to fetch available dates"
}
```
**Fix**: Check server logs or contact backend team

---

## 💡 Frontend Implementation Tips

### 1. Load Available Dates on Component Mount
```javascript
useEffect(() => {
  fetch('/api/v1/tenderiq/dates')
    .then(res => res.json())
    .then(data => {
      // data.dates is array of ScrapeDateInfo
      // Use for date selector dropdown
      setAvailableDates(data.dates);
    });
}, []);
```

### 2. Fetch Tenders with Date Filter
```javascript
const fetchTenders = async (selectedDate) => {
  const url = new URL('/api/v1/tenderiq/tenders', baseURL);
  url.searchParams.append('date', selectedDate); // YYYY-MM-DD

  const response = await fetch(url);
  const data = await response.json();
  // data.tenders is array of TenderResponseForFiltering
  // data.total_count is total
  // data.filtered_by shows what filters were applied
  return data;
};
```

### 3. Handle Date Validation
```javascript
const isValidDate = (dateStr) => {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (!regex.test(dateStr)) return false;
  return !isNaN(new Date(dateStr).getTime());
};

if (isValidDate(userInput)) {
  fetchTenders(userInput);
}
```

### 4. Display Tender Count per Date
```javascript
// From /dates endpoint, each date has tender_count
availableDates.map(date => (
  <DateOption key={date.date}>
    {date.date_str} ({date.tender_count} tenders)
  </DateOption>
))
```

### 5. Handle Empty Results
```javascript
const response = await fetch('/api/v1/tenderiq/tenders?date_range=last_1_day');
if (!response.ok) {
  // Show error message
  setError('Failed to fetch tenders');
} else {
  const data = await response.json();
  if (data.total_count === 0) {
    setMessage('No tenders found with selected filters');
  } else {
    setTenders(data.tenders);
  }
}
```

---

## 🔍 Field Reference

### TenderResponseForFiltering Fields

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `id` | UUID | `550e8400-...` | Unique identifier |
| `tender_id_str` | string | `TEN-2024-001` | Tender reference ID |
| `tender_name` | string | `Construction Project` | Display name |
| `tender_url` | string | `https://...` | Link to tender details |
| `city` | string | `Mumbai` | Location |
| `value` | string | `250 Crore` | **Note: string, not number** |
| `due_date` | string | `2024-11-15` | Bidding deadline |
| `summary` | string | `...` | Brief description |
| `query_name` | string (optional) | `Civil` | Category/query name |
| `tender_type` | string (optional) | `Open` | Type of tender |
| `state` | string (optional) | `Maharashtra` | State |
| `publish_date` | string (optional) | `2024-11-03` | Publication date |
| `last_date_of_bid_submission` | string (optional) | `2024-11-15` | Last submission date |
| `tender_value` | string (optional) | `250 Crore` | Value (duplicate of `value`) |

---

## 📊 Response Fields

### FilteredTendersResponse

| Field | Type | Description |
|-------|------|-------------|
| `tenders` | array | List of tender objects |
| `total_count` | integer | Total number of tenders returned |
| `filtered_by` | object | Applied filters metadata (e.g., `{"date_range": "last_5_days"}`) |
| `available_dates` | array | All available dates as YYYY-MM-DD strings |

---

## 🚀 Performance Notes

- `/dates` endpoint caches well (changes only daily) → Consider client-side caching
- `/tenders?include_all_dates=true` may be slow with large datasets → Use date filters when possible
- Results are paginated in memory (Phase 6 feature) → Suggest 50-100 items per view
- Date format validation happens server-side → Send valid YYYY-MM-DD format

---

## 🔗 Related Documentation

- **Full Implementation**: `TENDERIQ_IMPLEMENTATION_COMPLETE.md`
- **API Roadmap**: `TENDERIQ_DATE_FILTERING_ROADMAP.md`
- **Architecture Details**: `TENDERIQ_IMPLEMENTATION_ARCHITECTURE.md`

---

## ✅ Testing the API

### Using cURL

```bash
# Get available dates
curl "http://localhost:8000/api/v1/tenderiq/dates"

# Get tenders from last 5 days
curl "http://localhost:8000/api/v1/tenderiq/tenders?date_range=last_5_days"

# Get Civil tenders from specific date
curl "http://localhost:8000/api/v1/tenderiq/tenders?date=2024-11-03&category=Civil"

# Get all tenders with location filter
curl "http://localhost:8000/api/v1/tenderiq/tenders?include_all_dates=true&location=Mumbai"
```

### Using JavaScript Fetch
```javascript
// Get tenders with date range
const response = await fetch(
  '/api/v1/tenderiq/tenders?date_range=last_5_days'
);
const data = await response.json();
console.log(`Found ${data.total_count} tenders`);
data.tenders.forEach(tender => {
  console.log(`${tender.tender_name} - ${tender.value}`);
});
```

---

## 📞 Support

If you encounter issues:

1. **400 Bad Request**: Check date format (YYYY-MM-DD) and date_range values
2. **404 Not Found**: Verify data exists in database (scraper should have run)
3. **Slow Response**: Try narrower date ranges instead of `include_all_dates=true`
4. **Missing Fields**: Some fields are optional (marked with `Optional` in models)

---

*Last Updated: November 3, 2025*
*API Status: ✅ Production Ready*
