# Electronics Scraper - Data Structure Examples

## API Response Examples

### 1. Main Categories Response Structure

**Request URL**: `https://www.q84sale.com/ar/electronics/1`

**Response** (from `__NEXT_DATA__`):
```json
{
  "props": {
    "pageProps": {
      "verticalSubcats": [
        {
          "id": 99,
          "parent_id": 847,
          "slug": "mobile-phones-and-accessories",
          "name_ar": "موبايلات و إكسسوارات",
          "name_en": "Mobile Phones & Accessories",
          "image": "https://static.q84sale.com/images/cat_image/image_1_1_99.png",
          "featured_image": "https://static.q84sale.com/images/cat_image/image_16_9_99.png",
          "listings_count": 474,
          "display_order": 10,
          "category_type": "listings_full_filtration",
          "classification": "",
          "slug_url": "electronics/mobile-phones-and-accessories/1",
          "category_parent_slug": "electronics"
        },
        {
          "id": 2466,
          "parent_id": 847,
          "slug": "cameras",
          "name_ar": "كاميرات",
          "name_en": "Cameras",
          "listings_count": 871,
          "category_type": "sub_categories",
          "slug_url": "electronics/cameras",
          "category_parent_slug": "electronics"
        },
        {
          "id": 1568,
          "parent_id": 847,
          "slug": "smartwatches",
          "name_ar": "ساعات ذكية",
          "name_en": "Smartwatches",
          "listings_count": 78,
          "category_type": "listings",
          "slug_url": "electronics/smartwatches/1",
          "category_parent_slug": "electronics"
        }
      ]
    }
  }
}
```

### 2. Case 1: Category with catChilds

**Request URL**: `https://www.q84sale.com/ar/electronics/mobile-phones-and-accessories/1`

**Response**:
```json
{
  "props": {
    "pageProps": {
      "catChilds": [
        {
          "id": 2285,
          "parent_id": 99,
          "slug": "iphone-2285",
          "name_ar": "ايفون",
          "name_en": "IPhone",
          "listings_count": 332,
          "display_order": 10,
          "category_type": "listings",
          "slug_url": "electronics/mobile-phones-and-accessories/iphone-2285/1",
          "category_parent_slug": "mobile-phones-and-accessories"
        },
        {
          "id": 837,
          "parent_id": 99,
          "slug": "samsung",
          "name_ar": "سامسونغ",
          "name_en": "Samsung",
          "listings_count": 20,
          "display_order": 20,
          "slug_url": "electronics/mobile-phones-and-accessories/samsung/1",
          "category_parent_slug": "mobile-phones-and-accessories"
        },
        {
          "id": 2330,
          "parent_id": 99,
          "slug": "huawei",
          "name_ar": "هواوي",
          "name_en": "Huawei",
          "listings_count": 11,
          "display_order": 30,
          "slug_url": "electronics/mobile-phones-and-accessories/huawei/1",
          "category_parent_slug": "mobile-phones-and-accessories"
        },
        {
          "id": 49,
          "parent_id": 99,
          "slug": "other-phones",
          "name_ar": "موبايلات أخرى",
          "name_en": "Other Phones",
          "listings_count": 71,
          "display_order": 40,
          "slug_url": "electronics/mobile-phones-and-accessories/other-phones/1",
          "category_parent_slug": "mobile-phones-and-accessories"
        },
        {
          "id": 2817,
          "parent_id": 99,
          "slug": "mobile-accessories",
          "name_ar": "اكسسوارات",
          "name_en": "Accessories",
          "listings_count": 20,
          "display_order": 80,
          "slug_url": "electronics/mobile-phones-and-accessories/mobile-accessories/1",
          "category_parent_slug": "mobile-phones-and-accessories"
        }
      ]
    }
  }
}
```

### 3. Case 2: Category with Subcategories

**Request URL**: `https://www.q84sale.com/ar/electronics/cameras/1`

**Response**:
```json
{
  "props": {
    "pageProps": {
      "subcategories": [
        {
          "id": 1777,
          "parent_id": 2466,
          "slug": "monitoring-cameras",
          "name_ar": "كاميرات مراقبة",
          "name_en": "Monitoring Cameras",
          "listings_count": 778,
          "display_order": 10,
          "category_type": "listings",
          "slug_url": "electronics/cameras/monitoring-cameras/1",
          "category_parent_slug": "cameras",
          "is_leaf": true
        },
        {
          "id": 135,
          "parent_id": 2466,
          "slug": "digital-cameras",
          "name_ar": "كاميرات ديجيتال",
          "name_en": "Digital Cameras",
          "listings_count": 12,
          "display_order": 20,
          "slug_url": "electronics/cameras/digital-cameras/1",
          "category_parent_slug": "cameras",
          "is_leaf": true
        },
        {
          "id": 2822,
          "parent_id": 2466,
          "slug": "professional-cameras",
          "name_ar": "كاميرات إحترافية",
          "name_en": "Professional Cameras",
          "listings_count": 81,
          "display_order": 30,
          "slug_url": "electronics/cameras/professional-cameras/1",
          "category_parent_slug": "cameras",
          "is_leaf": true
        }
      ]
    }
  }
}
```

### 4. Case 3: Direct Listings Category

**Request URL**: `https://www.q84sale.com/ar/electronics/smartwatches/1`

**Response** (No catChilds or subcategories - goes straight to listings):
```json
{
  "props": {
    "pageProps": {
      "totalPages": 4,
      "listings": [
        {
          "id": 20494872,
          "title": "Apple Watch Series 9 45mm",
          "slug": "apple-watch-series-9-20494872",
          "price": 125,
          "image": "https://media.q84sale.com/images/user_adv/resize1000/1766407963263958472.jpg",
          "date_published": "2025-12-22 13:00:50",
          "cat_id": 3601,
          "cat_en_name": "Apple Watch",
          "cat_ar_name": "أبل ووتش",
          "user": {
            "user_id": 2349700,
            "name": "Tech Store"
          },
          "contact_no": ["96596962567"],
          "district_name": "حولي",
          "status": "normal",
          "images_count": 5
        }
      ]
    }
  }
}
```

## Listing Page Response

**Request URL**: `https://www.q84sale.com/ar/electronics/mobile-phones-and-accessories/iphone-2285/1`

**Response**:
```json
{
  "props": {
    "pageProps": {
      "totalPages": 17,
      "listings": [
        {
          "id": 20494872,
          "title": "احصل علىiPhone 14 Pro بسعة تخزينية هائلة ولون مميز مع إكسسوارات مجانية",
          "phone": "96511010338",
          "is_pm_enabled": true,
          "should_hide_my_number": true,
          "user": {
            "user_id": 2349700,
            "name": "Unlimited Tech Office",
            "image": "https://media.q84sale.com/images/profile_images/1745475404370861188.png"
          },
          "contact_no": ["96596962567"],
          "contact": "96596962567",
          "slug": "iphone-14-20494872",
          "desc_en": "6.1 inch\n💾 Capacity: 1TB\n🎨 Color: Purple",
          "desc_ar": "📺 حجم الشاشة: 6.1 انش\n💾 السعة التخزينية: 1TB",
          "price": 189,
          "user_type": "normal",
          "cat_ar_name": "ايفون 14",
          "cat_en_name": "IPhone 14",
          "cat_id": 3039,
          "districts_ids": [51],
          "reg_id": 1,
          "status": "normal",
          "date_published": "2025-12-22 13:00:50",
          "date_sort": "2025-12-22 13:00:50",
          "images_count": 12,
          "image": "https://media.q84sale.com/images/user_adv/resize1000/1766407963263958472.jpg",
          "images_seo": {
            "images": [
              {
                "keywords_ar": "",
                "tags_en": "",
                "name": "1766407963263958472.jpg",
                "keywords_en": "",
                "tags_ar": ""
              }
            ]
          },
          "thumb": "https://media.q84sale.com/images/user_adv/resize450/1766407963263958472.jpg",
          "thumbs": [
            "https://media.q84sale.com/images/user_adv/resize450/1766407963263958472.jpg"
          ],
          "is_anon": 1,
          "expire_date": "2026-01-21 13:00:50",
          "plan_id": 58,
          "district_name_localize": {
            "ar": "حولي , حولي",
            "en": "Hawalli , Hawalli"
          },
          "district_name": "حولي , حولي",
          "reactions": {
            "total_count": 0,
            "reaction_types": []
          },
          "attrs": [
            {
              "id": "217",
              "val": 1071
            }
          ],
          "is_verified": true,
          "logo": "https://media.q84sale.com/images/profile_images/1745475404370861188.png",
          "isNewCar": false
        }
      ]
    }
  }
}
```

## Detail Page Response

**Request URL**: `https://www.q84sale.com/ar/listing/iphone-14-20494872`

**Response**:
```json
{
  "props": {
    "pageProps": {
      "listing": {
        "user_adv_id": 20494872,
        "slug": "iphone-14-20494872",
        "date_published": "2025-12-22 13:00:50",
        "date_created": "2025-12-22 13:00:49",
        "date_expired": "2026-01-21 13:00:50",
        "date_sort": "2025-12-22 13:00:50",
        "description": "📺 حجم الشاشة: 6.1 انش\n💾 السعة التخزينية: 1TB...",
        "title": "احصل علىiPhone 14 Pro بسعة تخزينية هائلة",
        "source": "4sale-electronics-office",
        "phone": "96511010338",
        "contacts": ["96596962567"],
        "is_private_message_enabled": true,
        "price": "189.900",
        "lon": 48.013729,
        "lat": 29.343458,
        "video_url": null,
        "user_view_count": 1,
        "website_url": "",
        "extra_info": {
          "type": "business",
          "location_info": {
            "landmarks": [],
            "lat": 29.34345888994594,
            "location": "exact",
            "lon": 48.013729823974714
          }
        },
        "district_id": 51,
        "images": [
          "https://media.q84sale.com/images/user_adv/resize1000/1766407963263958472.jpg"
        ],
        "regions_id": 1,
        "extra_attributes": [
          {
            "id": 217,
            "val": "1071",
            "size": null
          },
          {
            "id": 206,
            "val": "1050",
            "size": null
          }
        ],
        "listing_type": "normal",
        "is_hide_my_number": true,
        "category": {
          "cat_id": 3039,
          "name": "ايفون 14",
          "description": "",
          "breadcrumb": [
            {
              "id": "847",
              "slug": "electronics",
              "val": "إلكترونيات"
            },
            {
              "id": "99",
              "slug": "mobile-phones-and-accessories",
              "val": "موبايلات و إكسسوارات"
            },
            {
              "id": "2285",
              "slug": "iphone-2285",
              "val": "ايفون"
            },
            {
              "id": "3039",
              "slug": "iphone-14",
              "val": "ايفون 14"
            }
          ]
        },
        "user": {
          "user_id": 2349700,
          "allow_follow": true,
          "email": "Info@unlimited-tec.com",
          "first_name": "Unlimited Tech Office",
          "image": "https://media.q84sale.com/images/profile_images/1745475404370861188.png",
          "phone": "96511010338",
          "member_since": "2025-03-05T10:18:34.000000Z",
          "region_id": 1,
          "listings_count": 264,
          "user_type": "electronics-office",
          "is_verified": true
        },
        "attrsAndVals": [
          {
            "attrData": {
              "id": 217,
              "type": "drop_down",
              "name_ar": "سعة التخزين",
              "name_en": "Storage",
              "system_name": "Storage",
              "is_required": 1,
              "display_order": 10,
              "is_filterable": 1
            },
            "valData": {
              "id": 1071,
              "attribute_id": 217,
              "display_order": 60,
              "name_ar": "١ تيرا بايت",
              "name_en": "1TB",
              "parent_id": "NULL"
            }
          },
          {
            "attrData": {
              "id": 206,
              "type": "drop_down",
              "name_ar": "الحالة",
              "name_en": "Condition",
              "system_name": "Condition",
              "is_required": 0,
              "display_order": 100,
              "is_filterable": 1
            },
            "valData": {
              "id": 1050,
              "attribute_id": 206,
              "display_order": 20,
              "name_ar": "مستعمل",
              "name_en": "Used",
              "parent_id": "NULL"
            }
          }
        ]
      }
    }
  }
}
```

## Excel Output Examples

### Excel for Case 1 (catChilds): `mobile-phones-and-accessories.xlsx`

**Sheet: Info**
| Category | Structure Type | Total Children/Sheets | Total Listings | Saved to S3 Date |
|----------|---------------|-----------------------|----------------|------------------|
| موبايلات و إكسسوارات | catchilds | 5 | 474 | 2025-12-22 |

**Sheet: ايفون**
| id | title | price | date_published | user_name | district_name | images_count | specification_en |
|----|-------|-------|-----------------|-----------|---|---|---|
| 20494872 | احصل علىiPhone 14 Pro... | 189 | 2025-12-22 13:00:50 | Unlimited Tech | حولي | 12 | {"Storage": "1TB", "Condition": "Used"} |
| 20494758 | ايفون 16 كالجديد... | 185 | 2025-12-22 12:28:57 | Ostora phones | المنقف | 2 | {"Storage": "256GB", "Condition": "Like New"} |

**Sheet: سامسونغ**
| id | title | price | date_published | user_name | district_name | images_count |
|----|-------|-------|-----------------|-----------|---|---|
| ... | ... | ... | ... | ... | ... | ... |

### Excel for Case 2 (Subcategories): `cameras.xlsx`

**Sheet: Info**
| Category | Structure Type | Total Children/Sheets | Total Listings | Saved to S3 Date |
|----------|---------------|-----------------------|----------------|------------------|
| كاميرات | subcategories | 3 | 871 | 2025-12-22 |

**Sheet: كاميرات مراقبة**
| id | title | price | date_published | user_name | district_name |
|----|-------|-------|-----------------|-----------|---|
| 20494950 | HD Surveillance Camera... | 45 | 2025-12-22 11:30:00 | Security Pro | الكويت | 
| ... | ... | ... | ... | ... | ... |

**Sheet: كاميرات ديجيتال**
| id | title | price | date_published | user_name | district_name |
|----|-------|-------|-----------------|-----------|---|
| ... | ... | ... | ... | ... | ... |

### Excel for Case 3 (Direct): `smartwatches.xlsx`

**Sheet: Info**
| Category | Structure Type | Total Children/Sheets | Total Listings | Saved to S3 Date |
|----------|---------------|-----------------------|----------------|------------------|
| ساعات ذكية | direct | 1 | 78 | 2025-12-22 |

**Sheet: ساعات ذكية**
| id | title | price | date_published | user_name | district_name |
|----|-------|-------|-----------------|-----------|---|
| 20494872 | Apple Watch Series 9... | 125 | 2025-12-22 13:00:50 | Tech Store | حولي |
| 20494843 | Samsung Galaxy Watch... | 95 | 2025-12-22 12:45:00 | Smart Devices | السالمية |
| ... | ... | ... | ... | ... | ... |

## JSON Summary Output

```json
{
  "scraped_at": "2025-12-22T14:30:45.123456",
  "saved_to_s3_date": "2025-12-22",
  "total_main_categories": 17,
  "total_listings": 12847,
  "main_categories": [
    {
      "name_ar": "موبايلات و إكسسوارات",
      "name_en": "Mobile Phones & Accessories",
      "slug": "mobile-phones-and-accessories",
      "structure_type": "catchilds",
      "children_count": 5,
      "total_listings": 474
    },
    {
      "name_ar": "كاميرات",
      "name_en": "Cameras",
      "slug": "cameras",
      "structure_type": "subcategories",
      "children_count": 3,
      "total_listings": 871
    },
    {
      "name_ar": "ساعات ذكية",
      "name_en": "Smartwatches",
      "slug": "smartwatches",
      "structure_type": "direct",
      "children_count": 1,
      "total_listings": 78
    }
  ]
}
```

## Scraper Output Examples

### Console Output for Case 1
```
[1/17] Processing: موبايلات و إكسسوارات (mobile-phones-and-accessories)
Fetching electronics main categories...
  mobile-phones-and-accessories: Found 5 catChilds
[1/5] Processing child: ايفون
  Fetching listings for mobile-phones-and-accessories/iphone-2285 page 1...
  Found 20 listings on page 1 (Total Pages: 17)
  Fetching detailed information for 20 listings on page 1/17...
  ✓ Retrieved details for iphone-14-20494872
  ✓ Retrieved details for iphone-16-20494758
  ...
  Successfully fetched 20/20 detailed listings
  Processing 40 images...
  Image 0: 20494872_0.jpg ✓
  Image 1: 20494872_1.jpg ✓
  ...
Total listings for ايفون: 332 (across 17 pages)

[2/5] Processing child: سامسونغ
...

Total listings for موبايلات و إكسسوارات: 474 (across 5 children)
```

### Console Output for Case 3
```
[15/17] Processing: ساعات ذكية (smartwatches)
smartwatches: Direct listings (no children)
  Fetching listings for smartwatches page 1...
  Found 20 listings on page 1 (Total Pages: 4)
  Fetching detailed information for 20 listings on page 1/4...
  ✓ Retrieved details for apple-watch-series-9-20494872
  ...
  Total listings for ساعات ذكية: 78 (across 4 pages)
```

## Data Column Examples

### Extracted Attributes
```python
{
  "specification_en": '{"Storage": "1TB", "Condition": "Used", "Color": "Purple"}',
  "specification_ar": '{"سعة التخزين": "١ تيرا بايت", "الحالة": "مستعمل", "اللون": "بنفسجي"}',
  "Storage": "1TB",
  "Condition": "Used",
  "Color": "Purple",
  "سعة التخزين": "١ تيرا بايت",
  "الحالة": "مستعمل",
  "اللون": "بنفسجي"
}
```

### Complete Listing Record
```python
{
  "id": 20494872,
  "title": "احصل علىiPhone 14 Pro بسعة تخزينية هائلة...",
  "slug": "iphone-14-20494872",
  "price": "189.900",
  "date_published": "2025-12-22 13:00:50",
  "date_relative": "Just now",
  "images_count": 12,
  "s3_images": [
    "https://bucket.s3.us-east-1.amazonaws.com/4sale-data/electronics/year=2025/month=12/day=22/images/mobile-phones-and-accessories/20494872_0.jpg",
    "https://bucket.s3.us-east-1.amazonaws.com/4sale-data/electronics/year=2025/month=12/day=22/images/mobile-phones-and-accessories/20494872_1.jpg"
  ],
  "user_name": "Unlimited Tech Office",
  "user_email": "Info@unlimited-tec.com",
  "user_phone": "96511010338",
  "user_type": "electronics-office",
  "is_verified": true,
  "address": "حولي , حولي",
  "full_address": "الكويت --_-- حولي --_-- حولي",
  "full_address_en": "Kuwait --_-- Hawalli --_-- Hawalli",
  "latitude": 29.343458,
  "longitude": 48.013729,
  "Storage": "1TB",
  "Condition": "Used",
  "specification_en": '{"Storage": "1TB", "Condition": "Used"}',
  "specification_ar": '{"سعة التخزين": "١ تيرا بايت", "الحالة": "مستعمل"}'
}
```

This comprehensive structure allows for easy analysis, filtering, and integration with downstream systems.
