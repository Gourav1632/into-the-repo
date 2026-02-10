'use client';

import React from 'react';
import { getComplexityColor, getComplexityBgColor } from '@/lib/complexityColors';

export function ComplexityLegend() {
  const complexityLevels = [
    { level: 'low', label: 'Low (<5)', description: 'Simple, easy to understand' },
    { level: 'medium', label: 'Medium (5-10)', description: 'Moderate complexity' },
    { level: 'high', label: 'High (>10)', description: 'Complex, harder to understand' },
  ] as const;

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900/50 backdrop-blur-sm p-4">
      <h3 className="text-sm font-semibold text-neutral-200 mb-3">Complexity Legend</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {complexityLevels.map((item) => (
          <div key={item.level} className="flex items-start gap-3">
            <div
              className="flex-shrink-0 w-3 h-3 rounded mt-0.5"
              style={{
                backgroundColor: getComplexityColor(
                  item.level === 'low' ? 2 : item.level === 'medium' ? 7 : 12
                ),
              }}
            />
            <div>
              <p className="text-xs font-medium text-neutral-300">{item.label}</p>
              <p className="text-xs text-neutral-400">{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
