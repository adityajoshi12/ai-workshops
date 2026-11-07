/**
 * Official Gemini Live API Tool Declarations
 *
 * Each function declaration strictly adheres to the @google/genai schema specification.
 * Gemini uses these declarations to generate structured functionCall events during the live audio stream.
 */

import { CATALOGUE } from './catalogue.js';

// Derived from the catalogue so new categories are automatically visible to Gemini.
const CATEGORIES = [...new Set(Object.values(CATALOGUE).map((p) => p.category))];

export const COMMERCE_FUNCTION_DECLARATIONS = [
  {
    name: 'search_products',
    description:
      'Searches the electronics catalogue (audio, smartphones, laptops, smartwatches, speakers, tablets, cameras, gaming, power banks, smart home) ' +
      'by keywords, category, budget, battery life and noise cancellation. Prefer `category` when the user names a product type.',
    parameters: {
      type: 'OBJECT',
      properties: {
        query: {
          type: 'STRING',
          description:
            'Short keywords, ALL of which must match. ALWAYS include the product type the user asked for ' +
            '(e.g. "headphones", "phone", "watch", "speaker") together with any qualifier: "travel headphones", "gaming laptop", "5g phone". ' +
            'Never send a qualifier alone (e.g. just "travel"), it matches unrelated products.',
        },
        category: {
          type: 'STRING',
          description: 'Restrict results to one product category.',
          enum: CATEGORIES,
        },
        maxPriceInr: {
          type: 'NUMBER',
          description: 'Maximum budget in Indian Rupees (INR), e.g. 3000.',
        },
        minBatteryHours: {
          type: 'NUMBER',
          description: 'Minimum required battery life in hours, e.g. 40. Excludes products with no battery.',
        },
        ancRequired: {
          type: 'BOOLEAN',
          description: 'Set to true if active noise cancellation is explicitly required by the user.',
        },
      },
    },
  },
  {
    name: 'get_product_details',
    description: 'Retrieves comprehensive specifications, warranty, ratings, and customer reviews for a specific product ID.',
    parameters: {
      type: 'OBJECT',
      properties: {
        productId: {
          type: 'STRING',
          description: 'The unique product ID, e.g. "prod_tb_x", "prod_sw_pro".',
        },
      },
      required: ['productId'],
    },
  },
  {
    name: 'compare_products',
    description: 'Performs a side-by-side comparison between 2 or 3 products focusing on price, battery, noise cancellation, and weight.',
    parameters: {
      type: 'OBJECT',
      properties: {
        productIds: {
          type: 'ARRAY',
          description: 'Array of 2 to 3 product IDs to compare, e.g. ["prod_tb_x", "prod_sw_pro"].',
          items: { type: 'STRING' },
        },
      },
      required: ['productIds'],
    },
  },
  {
    name: 'check_inventory',
    description: 'Checks real-time warehouse stock availability and delivery lead times for a product.',
    parameters: {
      type: 'OBJECT',
      properties: {
        productId: {
          type: 'STRING',
          description: 'The product ID to verify in stock.',
        },
        pincode: {
          type: 'STRING',
          description: 'Delivery destination postal code (6 digits), e.g. "560103".',
        },
      },
      required: ['productId'],
    },
  },
  {
    name: 'add_to_cart',
    description: 'Adds a specified quantity of a product to the customer\'s active shopping cart.',
    parameters: {
      type: 'OBJECT',
      properties: {
        productId: {
          type: 'STRING',
          description: 'The product ID to add to cart.',
        },
        quantity: {
          type: 'INTEGER',
          description: 'Number of units to add (default 1).',
        },
      },
      required: ['productId'],
    },
  },
  {
    name: 'get_cart',
    description: 'Retrieves the customer\'s current shopping cart, including all items, quantities, subtotal, 18% GST, and grand total.',
    parameters: {
      type: 'OBJECT',
      properties: {},
    },
  },
  {
    name: 'check_delivery',
    description: 'Calculates the estimated delivery date, express cutoff times, and shipping fee for a postal pincode.',
    parameters: {
      type: 'OBJECT',
      properties: {
        pincode: {
          type: 'STRING',
          description: 'The 6-digit Indian postal code to evaluate (e.g. "560103").',
        },
      },
      required: ['pincode'],
    },
  },
  {
    name: 'get_saved_addresses',
    description: 'Retrieves the customer\'s verified saved delivery addresses on file (Home, Office).',
    parameters: {
      type: 'OBJECT',
      properties: {},
    },
  },
  {
    name: 'place_order',
    description: 'Finalizes the purchase and creates a confirmed order record. CRITICAL: The assistant MUST obtain explicit verbal confirmation from the user (reading out item, address, and total) before invoking this function.',
    parameters: {
      type: 'OBJECT',
      properties: {
        addressId: {
          type: 'STRING',
          description: 'The selected delivery address ID, e.g. "addr_blr_home".',
        },
        paymentMethod: {
          type: 'STRING',
          description: 'Payment method, e.g. "Google Pay (UPI)" or "Saved Credit Card".',
        },
        userConfirmed: {
          type: 'BOOLEAN',
          description: 'Must be true only if the user explicitly said "yes", "confirm", or "place order" after hearing the total.',
        },
      },
      required: ['userConfirmed'],
    },
  },
];
