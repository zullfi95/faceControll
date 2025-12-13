import React, { useState } from 'react';
import { ChevronUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline';

const Table = ({
  columns,
  data,
  onRowClick,
  emptyMessage = 'Нет данных',
  className = '',
  caption,
  'aria-label': ariaLabel,
  'aria-describedby': ariaDescribedBy,
  ...props
}) => {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };
  
  const sortedData = React.useMemo(() => {
    if (!sortConfig.key) return data;
    
    return [...data].sort((a, b) => {
      const aValue = a[sortConfig.key];
      const bValue = b[sortConfig.key];
      
      if (aValue === null || aValue === undefined) return 1;
      if (bValue === null || bValue === undefined) return -1;
      
      if (typeof aValue === 'string') {
        return sortConfig.direction === 'asc'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }
      
      return sortConfig.direction === 'asc' ? aValue - bValue : bValue - aValue;
    });
  }, [data, sortConfig]);
  
  return (
    <div className={`overflow-x-auto ${className}`} role="region" aria-label={ariaLabel || "Таблица данных"} aria-describedby={ariaDescribedBy}>
      <table className="min-w-full divide-y divide-gray-200" role="table" aria-label={ariaLabel} {...props}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-gray-50" role="rowgroup">
          <tr role="row">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                role="columnheader"
                className={`
                  px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider
                  ${column.sortable ? 'cursor-pointer hover:bg-gray-100 focus:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] focus:ring-inset' : ''}
                `}
                onClick={() => column.sortable && handleSort(column.key)}
                tabIndex={column.sortable ? 0 : -1}
                aria-sort={column.sortable && sortConfig.key === column.key
                  ? (sortConfig.direction === 'asc' ? 'ascending' : 'descending')
                  : 'none'
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    column.sortable && handleSort(column.key);
                  }
                }}
              >
                <div className="flex items-center gap-2">
                  {column.label}
                  {column.sortable && sortConfig.key === column.key && (
                    sortConfig.direction === 'asc' ? (
                      <ChevronUpIcon className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <ChevronDownIcon className="h-4 w-4" aria-hidden="true" />
                    )
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200" role="rowgroup">
          {sortedData.length === 0 ? (
            <tr role="row">
              <td
                colSpan={columns.length}
                className="px-6 py-12 text-center text-gray-500"
                role="cell"
                aria-colspan={columns.length}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            sortedData.map((row, index) => (
              <tr
                key={index}
                role="row"
                onClick={() => onRowClick && onRowClick(row)}
                className={onRowClick ? 'cursor-pointer hover:bg-gray-50 transition-colors focus:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[rgb(19,91,147)] focus:ring-inset' : ''}
                tabIndex={onRowClick ? 0 : -1}
                onKeyDown={(e) => {
                  if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault();
                    onRowClick(row);
                  }
                }}
              >
                {columns.map((column) => (
                  <td key={column.key} role="cell" className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {column.render ? column.render(row[column.key], row) : row[column.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};

export default Table;

