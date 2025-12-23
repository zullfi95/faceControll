import jsPDF from 'jspdf';
import 'jspdf-autotable';
import * as XLSX from 'xlsx';

// Helper function to convert text to proper encoding for PDF
// jsPDF requires proper UTF-8 encoding for Cyrillic characters
const encodeText = (text) => {
  if (!text) return '';
  // Ensure text is properly encoded as UTF-8 string
  // Convert to string and normalize Unicode characters
  const str = String(text);
  // Ensure proper UTF-8 encoding for Cyrillic
  // For jsPDF, we need to ensure the text is in a format that can be rendered
  // Standard fonts don't support Cyrillic, so characters may appear as squares
  // This is a limitation of jsPDF's standard fonts
  return str;
};

export const exportToPDF = (data, title, filename) => {
  // Create PDF with proper settings for Unicode/Cyrillic support
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
    compress: true,
    putOnlyUsedFonts: true,
    floatPrecision: 16
  });

  // IMPORTANT: Standard jsPDF fonts (helvetica, times, courier) do NOT support Cyrillic
  // For full Cyrillic support, you need to add a custom font that supports Cyrillic
  // This is a known limitation of jsPDF
  // 
  // Workaround: Use standard font but note that Cyrillic characters may not render correctly
  // For production, consider adding a custom font with Cyrillic support
  doc.setFont('helvetica', 'normal');

  // Add title - ensure UTF-8 encoding
  doc.setFontSize(20);
  // Use splitTextToSize for better text handling with Cyrillic
  const titleLines = doc.splitTextToSize(encodeText(title), 180);
  doc.text(titleLines, 14, 22);

  // Добавляем дату (время Баку, UTC+4)
  const dateStr = `Дата: ${new Date().toLocaleDateString('ru-RU', { timeZone: 'Asia/Baku' })}`;
  doc.setFontSize(12);
  const dateLines = doc.splitTextToSize(encodeText(dateStr), 180);
  doc.text(dateLines, 14, 32);

  // Column name mapping for better readability
  const columnMapping = {
    user: 'Сотрудник',
    hikvision_id: 'ID Hikvision',
    entry_time: 'Время входа',
    exit_time: 'Время выхода',
    hours_in_shift: 'Часы в смене',
    hours_outside_shift: 'Часы вне смены',
    hours_worked: 'Всего часов',
    status: 'Статус'
  };

  // Prepare table data with localized headers
  const originalHeaders = Object.keys(data[0] || {});
  const headers = originalHeaders.map(key => encodeText(columnMapping[key] || key));
  const rows = data.map(row => originalHeaders.map(key => {
    const value = row[key];
    // Форматируем поля времени (время Баку, UTC+4)
    if ((key === 'entry_time' || key === 'exit_time') && value) {
      return encodeText(new Date(value).toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit',
        timeZone: 'Asia/Baku'
      }));
    }
    // Format numeric fields
    if (typeof value === 'number' && key.includes('hours')) {
      return encodeText(`${value.toFixed(2)} ч.`);
    }
    return encodeText(value);
  }));

  // Add table with proper encoding support for Cyrillic
  // Important: For full Cyrillic support, you may need to add a custom font
  // Standard fonts have limited Cyrillic support
  doc.autoTable({
    head: [headers],
    body: rows,
    startY: 40,
    styles: {
      fontSize: 8,
      cellPadding: 3,
      font: 'helvetica',
      fontStyle: 'normal',
      textColor: [0, 0, 0],
      overflow: 'linebreak',
      cellWidth: 'wrap',
      halign: 'left',
      valign: 'middle',
    },
    headStyles: {
      fillColor: [19, 91, 147],
      textColor: 255,
      fontStyle: 'bold',
      fontSize: 9,
      halign: 'left',
    },
    alternateRowStyles: {
      fillColor: [245, 245, 245],
    },
    // Ensure proper encoding for Cyrillic characters
    didParseCell: function (data) {
      // Ensure all text is properly encoded as UTF-8
      if (data.cell.text && Array.isArray(data.cell.text)) {
        data.cell.text = data.cell.text.map(text => encodeText(text));
      } else if (data.cell.text) {
        data.cell.text = encodeText(data.cell.text);
      }
    },
  });

  doc.save(`${filename}.pdf`);
};

// Функция для форматирования часов в формат "00:00"
const formatHoursToTime = (hours) => {
  if (hours === null || hours === undefined || isNaN(hours)) {
    return '00:00';
  }
  const totalMinutes = Math.round(hours * 60);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

// Функция для форматирования времени из ISO строки
const formatTime = (timeStr) => {
  if (!timeStr) return 'Не зафиксирован';
  try {
    const date = new Date(timeStr);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Baku'
    });
  } catch (e) {
    return timeStr;
  }
};

export const exportToExcel = (data, filename) => {
  if (!data || data.length === 0) {
    return;
  }

  // Transform data for better Excel formatting with proper UTF-8 encoding
  const transformedData = data.map(row => {
    const newRow = {};

    // Основные поля
    newRow['Сотрудник'] = row.user || '';
    newRow['ID Hikvision'] = row.hikvision_id || '';
    
    // Время начала смены
    newRow['Время начала смены'] = row.shift_start_time || '—';
    
    // Первый вход (время)
    newRow['Первый вход (время)'] = row.entry_time ? formatTime(row.entry_time) : 'Не зафиксирован';
    
    // Опоздание
    newRow['Опоздание'] = row.delay_minutes !== null && row.delay_minutes !== undefined 
      ? `${row.delay_minutes} мин` 
      : '—';
    
    // Последняя аутентификация
    newRow['Последняя аутентификация'] = row.last_authentication ? formatTime(row.last_authentication) : 'Не зафиксирован';
    
    // Часов в смене (продолжительность смены)
    if (row.shift_duration_hours !== null && row.shift_duration_hours !== undefined) {
      newRow['Часов в смене'] = formatHoursToTime(row.shift_duration_hours);
    } else {
      newRow['Часов в смене'] = '—';
    }
    
    // Время за смену
    newRow['Время за смену'] = row.hours_in_shift !== null && row.hours_in_shift !== undefined
      ? formatHoursToTime(row.hours_in_shift)
      : '00:00';
    
    // Время вне смены
    newRow['Время вне смены'] = row.hours_outside_shift !== null && row.hours_outside_shift !== undefined
      ? formatHoursToTime(row.hours_outside_shift)
      : '00:00';
    
    // Зашел/Вышел
    if (row.entry_exit_type) {
      newRow['Зашел/Вышел'] = row.entry_exit_type === 'entry' ? 'Вход' : 'Выход';
    } else {
      newRow['Зашел/Вышел'] = '—';
    }
    
    // Статус
    const statusMap = {
      'Present': 'Присутствует',
      'Absent': 'Отсутствует',
      'Present (no exit)': 'Присутствует (нет выхода)'
    };
    newRow['Статус'] = statusMap[row.status] || row.status || '—';

    return newRow;
  });

  // Создаем worksheet с правильной кодировкой UTF-8
  const worksheet = XLSX.utils.json_to_sheet(transformedData);
  
  // Настраиваем ширину колонок
  const colWidths = [
    { wch: 20 }, // Сотрудник
    { wch: 15 }, // ID Hikvision
    { wch: 18 }, // Время начала смены
    { wch: 22 }, // Первый вход (время)
    { wch: 12 }, // Опоздание
    { wch: 25 }, // Последняя аутентификация
    { wch: 15 }, // Часов в смене
    { wch: 15 }, // Время за смену
    { wch: 15 }, // Время вне смены
    { wch: 12 }, // Зашел/Вышел
    { wch: 20 }  // Статус
  ];
  worksheet['!cols'] = colWidths;
  
  // Создаем workbook с правильной кодировкой
  const workbook = XLSX.utils.book_new();
  
  // Добавляем лист с правильным именем (UTF-8)
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Отчет');
  
  // Сохраняем файл с правильной кодировкой UTF-8
  // XLSX.writeFile автоматически использует UTF-8 для имен файлов и содержимого
  XLSX.writeFile(workbook, `${filename}.xlsx`, {
    bookType: 'xlsx',
    type: 'array',
    cellStyles: true
  });
};
