import jsPDF from 'jspdf';
import 'jspdf-autotable';
import * as XLSX from 'xlsx';

export const exportToPDF = (data, title, filename) => {
  const doc = new jsPDF();

  // Add title
  doc.setFontSize(20);
  doc.text(title, 14, 22);

  // Add date (время Баку, UTC+4)
  doc.setFontSize(12);
  doc.text(`Дата: ${new Date().toLocaleDateString('ru-RU', { timeZone: 'Asia/Baku' })}`, 14, 32);

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
  const headers = originalHeaders.map(key => columnMapping[key] || key);
  const rows = data.map(row => originalHeaders.map(key => {
    const value = row[key];
    // Format time fields (время Баку, UTC+4)
    if ((key === 'entry_time' || key === 'exit_time') && value) {
      return new Date(value).toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit',
        timeZone: 'Asia/Baku'
      });
    }
    // Format numeric fields
    if (typeof value === 'number' && key.includes('hours')) {
      return `${value.toFixed(2)} ч.`;
    }
    return value;
  }));

  // Add table
  doc.autoTable({
    head: [headers],
    body: rows,
    startY: 40,
    styles: {
      fontSize: 8,
      cellPadding: 3,
    },
    headStyles: {
      fillColor: [19, 91, 147],
      textColor: 255,
    },
    alternateRowStyles: {
      fillColor: [245, 245, 245],
    },
  });

  doc.save(`${filename}.pdf`);
};

export const exportToExcel = (data, filename) => {
  // Transform data for better Excel formatting
  const transformedData = data.map(row => {
    const newRow = { ...row };

    // Format time fields (время Баку, UTC+4)
    if (row.entry_time) {
      newRow['Время входа'] = new Date(row.entry_time).toLocaleTimeString('ru-RU', {
        hour: '2-digit', 
        minute: '2-digit',
        timeZone: 'Asia/Baku'
      });
    }
    if (row.exit_time) {
      newRow['Время выхода'] = new Date(row.exit_time).toLocaleTimeString('ru-RU', {
        hour: '2-digit', 
        minute: '2-digit',
        timeZone: 'Asia/Baku'
      });
    }

    // Format hours fields
    if (row.hours_in_shift !== undefined) {
      newRow['Часы в смене'] = `${row.hours_in_shift.toFixed(2)} ч.`;
    }
    if (row.hours_outside_shift !== undefined) {
      newRow['Часы вне смены'] = `${row.hours_outside_shift.toFixed(2)} ч.`;
    }
    if (row.hours_worked !== undefined) {
      newRow['Всего часов'] = `${row.hours_worked.toFixed(2)} ч.`;
    }

    // Rename columns to Russian
    newRow['Сотрудник'] = row.user;
    newRow['ID Hikvision'] = row.hikvision_id;
    newRow['Статус'] = row.status;

    // Remove original columns
    delete newRow.user;
    delete newRow.hikvision_id;
    delete newRow.entry_time;
    delete newRow.exit_time;
    delete newRow.hours_in_shift;
    delete newRow.hours_outside_shift;
    delete newRow.hours_worked;
    delete newRow.status;

    return newRow;
  });

  const worksheet = XLSX.utils.json_to_sheet(transformedData);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Отчет');
  XLSX.writeFile(workbook, `${filename}.xlsx`);
};
