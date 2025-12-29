import React, { useState, useMemo } from 'react';
import { ChevronUpIcon, ChevronDownIcon, MagnifyingGlassIcon, XMarkIcon, ChevronDownIcon as DropdownIcon } from '@heroicons/react/24/outline';
import Dropdown, { DropdownItem } from './Dropdown';

const DataTable = ({
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
  const [filters, setFilters] = useState({});

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const handleFilter = (key, value) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const clearFilter = (key) => {
    setFilters(prev => {
      const newFilters = { ...prev };
      delete newFilters[key];
      return newFilters;
    });
  };

  const clearAllFilters = () => {
    setFilters({});
  };

  // Фильтрация данных
  const filteredData = useMemo(() => {
    if (Object.keys(filters).length === 0) return data;

    console.log('Filtering data with active filters:', filters);

    return data.filter(row => {
      const result = Object.entries(filters).every(([key, filterValue]) => {
        if (!filterValue || filterValue.trim() === '') return true;

        const cellValue = row[key];
        const column = columns.find(col => col.key === key);
        const isSelectFilter = column && column.filterType === 'select';

        console.log(`Checking row ${row.id}: key=${key}, filterValue="${filterValue}", cellValue="${cellValue}", isSelect=${isSelectFilter}`);

        // Для null/undefined значений
        if (cellValue === null || cellValue === undefined) {
          console.log('Cell value is null/undefined, skipping');
          return false;
        }

        const filter = filterValue.toLowerCase().trim();

        // Для select фильтров - точное совпадение
        if (isSelectFilter) {
          const matches = String(cellValue).toLowerCase() === filter;
          console.log(`Select filter comparison: "${String(cellValue).toLowerCase()}" === "${filter}" = ${matches}`);
          return matches;
        }

        // Для числовых полей - поддержка диапазонов (например: "10-20" или ">10" или "<20")
        if (typeof cellValue === 'number') {
          // Проверяем на диапазон (например: "10-20")
          const rangeMatch = filter.match(/^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$/);
          if (rangeMatch) {
            const min = parseFloat(rangeMatch[1]);
            const max = parseFloat(rangeMatch[2]);
            return cellValue >= min && cellValue <= max;
          }

          // Проверяем на больше (">10")
          const greaterMatch = filter.match(/^>\s*(\d+(?:\.\d+)?)$/);
          if (greaterMatch) {
            const threshold = parseFloat(greaterMatch[1]);
            return cellValue > threshold;
          }

          // Проверяем на меньше ("<20")
          const lessMatch = filter.match(/^<\s*(\d+(?:\.\d+)?)$/);
          if (lessMatch) {
            const threshold = parseFloat(lessMatch[1]);
            return cellValue < threshold;
          }

          // Точное совпадение для чисел
          const numValue = parseFloat(filter);
          if (!isNaN(numValue)) {
            return cellValue === numValue;
          }

          return false;
        }

        // Для строковых полей - поиск подстроки (case-insensitive)
        if (typeof cellValue === 'string') {
          return cellValue.toLowerCase().includes(filter);
        }

        // Для других типов - преобразование в строку и поиск
        return String(cellValue).toLowerCase().includes(filter);
      });
    });
  }, [data, filters]);

  // Сортировка отфильтрованных данных
  const sortedData = useMemo(() => {
    if (!sortConfig.key) return filteredData;

    return [...filteredData].sort((a, b) => {
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
  }, [filteredData, sortConfig]);

  // Собираем уникальные значения для select фильтров
  const filterOptions = useMemo(() => {
    const options = {};

    columns.forEach(column => {
      if (column.filterType === 'select') {
        const uniqueValues = new Set();

        data.forEach(row => {
          const value = row[column.key];
          if (value !== null && value !== undefined && value !== '') {
            uniqueValues.add(value);
          }
        });

        options[column.key] = Array.from(uniqueValues).sort((a, b) => {
          // Для строк - алфавитная сортировка
          if (typeof a === 'string' && typeof b === 'string') {
            return a.localeCompare(b);
          }
          return String(a).localeCompare(String(b));
        });
      }
    });

    // Отладка для диагностики проблем с фильтрами
    if (data.length > 0) {
      console.log('DataTable filterOptions:', options);
      console.log('DataTable data length:', data.length);
      console.log('DataTable filters:', filters);
      console.log('DataTable sample data:', data.slice(0, 2));
    }

    return options;
  }, [columns, data]);

  // Проверяем, есть ли активные фильтры
  const hasActiveFilters = Object.keys(filters).length > 0;

  return (
    <div className={`overflow-x-auto ${className}`} role="region" aria-label={ariaLabel || "Таблица данных с фильтрацией"} aria-describedby={ariaDescribedBy}>
      {/* Кнопка очистки всех фильтров */}
      {hasActiveFilters && (
        <div className="mb-4 flex justify-end">
          <button
            onClick={clearAllFilters}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            aria-label="Очистить все фильтры"
          >
            <XMarkIcon className="h-4 w-4" />
            Очистить фильтры ({Object.keys(filters).length})
          </button>
        </div>
      )}

      <table className="min-w-full divide-y divide-gray-200" role="table" aria-label={ariaLabel} {...props}>
        {caption && <caption className="sr-only">{caption}</caption>}

        {/* Заголовки с фильтрами */}
        <thead className="bg-gray-50" role="rowgroup">
          {/* Основные заголовки */}
          <tr role="row">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                role="columnheader"
                className={`
                  px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200
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

          {/* Строка с фильтрами */}
          <tr role="row" className="bg-gray-25">
            {columns.map((column) => (
              <th
                key={`filter-${column.key}`}
                scope="col"
                role="columnheader"
                className="px-6 py-2 border-b border-gray-200"
              >
                <div className="flex items-center gap-2">
                  {column.filterType === 'select' ? (
                    // Select фильтр для колонок с ограниченным набором значений
                    <div className="relative flex-1">
                      <Dropdown
                        trigger={
                          <button className="flex items-center justify-between w-full px-3 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 bg-white">
                            <span className={filters[column.key] ? 'text-gray-900' : 'text-gray-500'}>
                              {filters[column.key] || `Все ${column.label.toLowerCase()}`}
                            </span>
                            <DropdownIcon className="h-4 w-4 text-gray-400 ml-2" />
                          </button>
                        }
                        aria-label={`Фильтр по колонке ${column.label}`}
                      >
                        <DropdownItem onClick={() => handleFilter(column.key, '')}>
                          Все {column.label.toLowerCase()}
                        </DropdownItem>
                        {filterOptions[column.key]?.map((option) => (
                          <DropdownItem
                            key={option}
                            onClick={() => handleFilter(column.key, option)}
                          >
                            {option}
                          </DropdownItem>
                        ))}
                      </Dropdown>
                      {filters[column.key] && (
                        <button
                          onClick={() => clearFilter(column.key)}
                          className="absolute inset-y-0 right-0 pr-2 flex items-center"
                          aria-label={`Очистить фильтр для ${column.label}`}
                        >
                          <XMarkIcon className="h-4 w-4 text-gray-400 hover:text-gray-600" />
                        </button>
                      )}
                    </div>
                  ) : (
                    // Text input фильтр для колонок с произвольным текстом
                    <div className="relative flex-1">
                      <div className="absolute inset-y-0 left-0 pl-2 flex items-center pointer-events-none">
                        <MagnifyingGlassIcon className="h-4 w-4 text-gray-400" aria-hidden="true" />
                      </div>
                      <input
                        type="text"
                        placeholder={`Фильтр ${column.label.toLowerCase()}`}
                        value={filters[column.key] || ''}
                        onChange={(e) => handleFilter(column.key, e.target.value)}
                        className="block w-full pl-8 pr-8 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                        aria-label={`Фильтр по колонке ${column.label}`}
                      />
                      {filters[column.key] && (
                        <button
                          onClick={() => clearFilter(column.key)}
                          className="absolute inset-y-0 right-0 pr-2 flex items-center"
                          aria-label={`Очистить фильтр для ${column.label}`}
                        >
                          <XMarkIcon className="h-4 w-4 text-gray-400 hover:text-gray-600" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>

        {/* Тело таблицы */}
        <tbody className="bg-white divide-y divide-gray-200" role="rowgroup">
          {sortedData.length === 0 ? (
            <tr role="row">
              <td
                colSpan={columns.length}
                className="px-6 py-12 text-center text-gray-500"
                role="cell"
                aria-colspan={columns.length}
              >
                {hasActiveFilters ? 'Нет данных, соответствующих фильтрам' : emptyMessage}
              </td>
            </tr>
          ) : (
            sortedData.map((row, index) => (
              <tr
                key={row.id || index}
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

      {/* Информация о результатах */}
      <div className="mt-4 text-sm text-gray-600">
        Показано {sortedData.length} из {data.length} записей
        {hasActiveFilters && ` (применены фильтры: ${Object.keys(filters).length})`}
      </div>
    </div>
  );
};

export default DataTable;
