import React, { useState } from 'react';
import { FixedSizeList as List } from 'react-window';
import { ChevronUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline';

const VirtualizedTable = ({
  columns,
  data,
  height = 400,
  itemSize = 60,
  onRowClick,
  className = '',
  'aria-label': ariaLabel = 'Виртуализированная таблица',
  caption,
  headerClassName = '',
  rowClassName = '',
  ...props
}) => {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

  const handleSort = (key) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const sortedData = React.useMemo(() => {
    if (!sortConfig.key) return data;
    
    return [...data].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      
      if (aVal === bVal) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      
      const comparison = aVal < bVal ? -1 : 1;
      return sortConfig.direction === 'asc' ? comparison : -comparison;
    });
  }, [data, sortConfig]);

  const Row = ({ index, style }) => {
    const row = sortedData[index];
    if (!row) return null;
    
    return (
      <div
        style={style}
        onClick={() => onRowClick && onRowClick(row)}
        className={`
          border-b border-gray-200 hover:bg-gray-50 transition-colors duration-150
          ${onRowClick ? 'cursor-pointer' : ''}
          ${rowClassName}
        `}
        role="row"
        aria-rowindex={index + 2}
      >
        <div className="px-4 py-4 sm:px-6 flex items-center gap-4">
          {columns.map((column) => (
            <div 
              key={column.key} 
              className={column.className || 'flex-1 min-w-0'}
              style={column.width ? { width: column.width, flex: 'none' } : {}}
            >
              {column.render ? column.render(row[column.key], row, index) : (row[column.key] || '--')}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className={`bg-white border border-gray-200 rounded-lg overflow-hidden ${className}`} role="table" aria-label={ariaLabel}>
      {caption && <caption className="sr-only">{caption}</caption>}
      
      {/* Header */}
      <div className={`bg-gray-50 border-b border-gray-200 px-4 py-3 flex items-center gap-4 ${headerClassName}`} role="rowgroup">
        {columns.map((column) => (
          <div 
            key={column.key} 
            className={column.className || 'flex-1 min-w-0'}
            style={column.width ? { width: column.width, flex: 'none' } : {}}
            role="columnheader"
          >
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                {column.label}
              </span>
              {column.sortable && (
                <button 
                  onClick={() => handleSort(column.key)}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                  aria-label={`Сортировать по ${column.label}`}
                >
                  {sortConfig.key === column.key ? (
                    sortConfig.direction === 'asc' ? (
                      <ChevronUpIcon className="h-4 w-4" />
                    ) : (
                      <ChevronDownIcon className="h-4 w-4" />
                    )
                  ) : (
                    <ChevronUpIcon className="h-4 w-4 opacity-50" />
                  )}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Virtualized list */}
      {sortedData.length > 0 ? (
        <List
          height={height}
          itemCount={sortedData.length}
          itemSize={itemSize}
          role="rowgroup"
          {...props}
        >
          {Row}
        </List>
      ) : (
        <div className="px-4 py-8 text-center text-gray-500" role="row">
          Нет данных для отображения
        </div>
      )}
    </div>
  );
};

export default VirtualizedTable;

