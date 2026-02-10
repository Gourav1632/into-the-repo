/**
 * Utility functions for determining node styling based on complexity metrics.
 */

export type ComplexityLevel = 'low' | 'medium' | 'high';

/**
 * Determine complexity level based on complexity score.
 * 
 * @param complexity - Numeric complexity score
 * @returns Complexity level: 'low' (< 5), 'medium' (5-10), 'high' (> 10)
 */
export function getComplexityLevel(complexity: number | undefined): ComplexityLevel {
  if (complexity === undefined || complexity === null) return 'medium';
  if (complexity < 5) return 'low';
  if (complexity <= 10) return 'medium';
  return 'high';
}

/**
 * Get color based on complexity level.
 * 
 * @param complexity - Numeric complexity score
 * @returns Color string for the node
 */
export function getComplexityColor(complexity: number | undefined): string {
  const level = getComplexityLevel(complexity);
  
  switch (level) {
    case 'low':
      return '#10b981'; // Green
    case 'medium':
      return '#f59e0b'; // Amber
    case 'high':
      return '#ef4444'; // Red
    default:
      return '#6b7280'; // Gray
  }
}

/**
 * Get background color (lighter variant) based on complexity.
 * 
 * @param complexity - Numeric complexity score
 * @returns Background color string
 */
export function getComplexityBgColor(complexity: number | undefined): string {
  const level = getComplexityLevel(complexity);
  
  switch (level) {
    case 'low':
      return '#ecfdf5'; // Light green
    case 'medium':
      return '#fffbeb'; // Light amber
    case 'high':
      return '#fef2f2'; // Light red
    default:
      return '#f3f4f6'; // Light gray
  }
}

/**
 * Get border color based on complexity.
 * 
 * @param complexity - Numeric complexity score
 * @returns Border color string
 */
export function getComplexityBorderColor(complexity: number | undefined): string {
  const level = getComplexityLevel(complexity);
  
  switch (level) {
    case 'low':
      return '#d1fae5'; // Light green border
    case 'medium':
      return '#fef3c7'; // Light amber border
    case 'high':
      return '#fecaca'; // Light red border
    default:
      return '#e5e7eb'; // Light gray border
  }
}

/**
 * Get text color based on complexity level.
 * 
 * @param complexity - Numeric complexity score
 * @returns Text color string
 */
export function getComplexityTextColor(complexity: number | undefined): string {
  const level = getComplexityLevel(complexity);
  
  switch (level) {
    case 'low':
      return '#047857'; // Dark green
    case 'medium':
      return '#b45309'; // Dark amber
    case 'high':
      return '#991b1b'; // Dark red
    default:
      return '#374151'; // Dark gray
  }
}

/**
 * Get complexity label for display.
 * 
 * @param complexity - Numeric complexity score
 * @returns Readable complexity label
 */
export function getComplexityLabel(complexity: number | undefined): string {
  const level = getComplexityLevel(complexity);
  
  if (complexity === undefined || complexity === null) {
    return 'Unknown complexity';
  }
  
  switch (level) {
    case 'low':
      return `Low (${complexity.toFixed(1)})`;
    case 'medium':
      return `Medium (${complexity.toFixed(1)})`;
    case 'high':
      return `High (${complexity.toFixed(1)})`;
    default:
      return 'Unknown';
  }
}
