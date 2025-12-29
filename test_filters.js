// Тест логики фильтрации
const testData = [
  { id: 1, shift_name: 'Дневная смена', status: 'Present', day_name: 'Понедельник' },
  { id: 2, shift_name: 'Ночная смена', status: 'Absent', day_name: 'Вторник' },
  { id: 3, shift_name: 'Дневная смена', status: 'Present', day_name: 'Понедельник' },
  { id: 4, shift_name: 'Дневная смена', status: 'Absent', day_name: 'Среда' }
];

// Тест сбора уникальных значений
function getFilterOptions(data, columns) {
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
        if (typeof a === 'string' && typeof b === 'string') {
          return a.localeCompare(b);
        }
        return String(a).localeCompare(String(b));
      });
    }
  });

  return options;
}

// Тест фильтрации
function filterData(data, filters, columns) {
  if (Object.keys(filters).length === 0) return data;

  return data.filter(row => {
    return Object.entries(filters).every(([key, filterValue]) => {
      if (!filterValue || filterValue.trim() === '') return true;

      const cellValue = row[key];
      const column = columns.find(col => col.key === key);
      const isSelectFilter = column && column.filterType === 'select';

      if (cellValue === null || cellValue === undefined) {
        return false;
      }

      const filter = filterValue.toLowerCase().trim();

      if (isSelectFilter) {
        return String(cellValue).toLowerCase() === filter;
      }

      if (typeof cellValue === 'string') {
        return cellValue.toLowerCase().includes(filter);
      }

      return String(cellValue).toLowerCase().includes(filter);
    });
  });
}

// Тест
const columns = [
  { key: 'shift_name', filterType: 'select' },
  { key: 'status', filterType: 'select' },
  { key: 'day_name', filterType: 'select' }
];

console.log('Test data:', testData);
console.log('Filter options:', getFilterOptions(testData, columns));

// Тест фильтрации по дневной смене
const filters = { shift_name: 'дневная смена' };
console.log('Filters:', filters);
console.log('Filtered data:', filterData(testData, filters, columns));
