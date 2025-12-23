import jsPDF from 'jspdf';
import 'jspdf-autotable';
import * as XLSX from 'xlsx';

// Helper function to format time
const formatTime = (timeStr) => {
  if (!timeStr) return 'N/A';
  try {
    const date = new Date(timeStr);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Asia/Baku'
    });
  } catch (e) {
    return timeStr;
  }
};

// Helper function to format date
const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: 'Asia/Baku'
    });
  } catch (e) {
    return dateStr;
  }
};

// Helper function to format hours
const formatHours = (hours) => {
  if (hours === null || hours === undefined || isNaN(hours)) return '0.00';
  return hours.toFixed(2);
};

// Helper function to get status text
const getStatusText = (status) => {
  const statusMap = {
    'Present': 'Present',
    'Absent': 'Absent',
    'Present (no exit)': 'Present (No Exit)'
  };
  return statusMap[status] || status || 'Unknown';
};

export const exportToPDF = (data, title, filename) => {
  if (!data || data.length === 0) {
    return;
  }

  // Create PDF with proper settings
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
    compress: true,
    putOnlyUsedFonts: true,
    floatPrecision: 16
  });

  doc.setFont('helvetica', 'normal');

  // Header section with company branding
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 14;
  let yPos = 15;

  // Header background
  doc.setFillColor(19, 91, 147);
  doc.rect(0, 0, pageWidth, 35, 'F');

  // Title
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text('ATTENDANCE REPORT', margin, yPos + 8);

  // Report date
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const reportDate = new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'Asia/Baku'
  });
  doc.text(`Generated: ${reportDate}`, margin, yPos + 15);

  // Report period (if available in data)
  if (data[0]?.report_date) {
    doc.text(`Report Date: ${formatDate(data[0].report_date)}`, margin, yPos + 20);
  }

  // Reset text color
  doc.setTextColor(0, 0, 0);
  yPos = 45;

  // Summary statistics
  const totalEmployees = data.length;
  const presentCount = data.filter(row => row.status === 'Present' || row.status === 'Present (no exit)').length;
  const absentCount = data.filter(row => row.status === 'Absent').length;
  const totalHours = data.reduce((sum, row) => sum + (row.hours_worked_total || 0), 0);

  // Summary box
  doc.setFillColor(245, 247, 250);
  doc.roundedRect(margin, yPos, pageWidth - 2 * margin, 20, 2, 2, 'F');
  
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.text('SUMMARY', margin + 2, yPos + 7);
  
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.text(`Total Employees: ${totalEmployees}`, margin + 2, yPos + 12);
  doc.text(`Present: ${presentCount}`, margin + 50, yPos + 12);
  doc.text(`Absent: ${absentCount}`, margin + 80, yPos + 12);
  doc.text(`Total Hours: ${formatHours(totalHours)}`, margin + 110, yPos + 12);

  yPos += 25;

  // Column headers mapping
  const columnMapping = {
    user: 'Employee Name',
    hikvision_id: 'Employee ID',
    shift_start_time: 'Shift Start',
    shift_duration_hours: 'Shift Duration',
    entry_time: 'First Entry',
    delay_minutes: 'Delay (min)',
    last_authentication: 'Last Event',
    hours_in_shift: 'Hours in Shift',
    hours_outside_shift: 'Hours Outside',
    hours_worked_total: 'Total Hours',
    status: 'Status'
  };

  // Prepare table data
  const columns = [
    'user',
    'hikvision_id',
    'shift_start_time',
    'entry_time',
    'delay_minutes',
    'hours_in_shift',
    'hours_outside_shift',
    'hours_worked_total',
    'status'
  ];

  const headers = columns.map(key => columnMapping[key] || key);
  const rows = data.map(row => {
    return columns.map(key => {
      const value = row[key];
      
      if (key === 'entry_time' || key === 'last_authentication') {
        return formatTime(value);
      }
      
      if (key === 'delay_minutes') {
        return value !== null && value !== undefined ? `${value}` : '—';
      }
      
      if (key === 'hours_in_shift' || key === 'hours_outside_shift' || key === 'hours_worked_total') {
        return formatHours(value);
      }
      
      if (key === 'status') {
        return getStatusText(value);
      }
      
      if (key === 'shift_start_time') {
        return value || '—';
      }
      
      return value || '—';
    });
  });

  // Add table with enhanced styling
  doc.autoTable({
    head: [headers],
    body: rows,
    startY: yPos,
    margin: { left: margin, right: margin },
    styles: {
      fontSize: 8,
      cellPadding: 2.5,
      font: 'helvetica',
      fontStyle: 'normal',
      textColor: [51, 51, 51],
      overflow: 'linebreak',
      cellWidth: 'wrap',
      halign: 'left',
      valign: 'middle',
      lineColor: [220, 220, 220],
      lineWidth: 0.1,
    },
    headStyles: {
      fillColor: [19, 91, 147],
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      fontSize: 9,
      halign: 'left',
      valign: 'middle',
      lineColor: [19, 91, 147],
      lineWidth: 0.1,
    },
    alternateRowStyles: {
      fillColor: [250, 250, 250],
    },
    columnStyles: {
      0: { cellWidth: 35 }, // Employee Name
      1: { cellWidth: 20 }, // Employee ID
      2: { cellWidth: 20 }, // Shift Start
      3: { cellWidth: 20 }, // First Entry
      4: { cellWidth: 15 }, // Delay
      5: { cellWidth: 18 }, // Hours in Shift
      6: { cellWidth: 18 }, // Hours Outside
      7: { cellWidth: 18 }, // Total Hours
      8: { cellWidth: 20 }, // Status
    },
    didDrawCell: function (data) {
      // Add status color coding
      if (data.section === 'body' && data.column.index === 8) {
        const status = data.cell.text[0];
        if (status === 'Present') {
          doc.setFillColor(220, 252, 231);
          doc.rect(data.cell.x, data.cell.y, data.cell.width, data.cell.height, 'F');
        } else if (status === 'Absent') {
          doc.setFillColor(254, 226, 226);
          doc.rect(data.cell.x, data.cell.y, data.cell.width, data.cell.height, 'F');
        } else if (status === 'Present (No Exit)') {
          doc.setFillColor(255, 237, 213);
          doc.rect(data.cell.x, data.cell.y, data.cell.width, data.cell.height, 'F');
        }
      }
    },
  });

  // Footer
  const finalY = doc.lastAutoTable.finalY || yPos;
  const pageHeight = doc.internal.pageSize.getHeight();
  
  doc.setFontSize(8);
  doc.setTextColor(128, 128, 128);
  doc.setFont('helvetica', 'italic');
  doc.text(
    `This report was generated automatically by Attendance Management System`,
    margin,
    pageHeight - 10
  );
  doc.text(
    `Page 1 of 1`,
    pageWidth - margin - 20,
    pageHeight - 10
  );

  // Save PDF
  doc.save(`${filename}.pdf`);
};

// Function to format hours to "HH:MM" format
const formatHoursToTime = (hours) => {
  if (hours === null || hours === undefined || isNaN(hours)) {
    return '00:00';
  }
  const totalMinutes = Math.round(hours * 60);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

// Function to format time from ISO string
const formatTimeExcel = (timeStr) => {
  if (!timeStr) return 'N/A';
  try {
    const date = new Date(timeStr);
    return date.toLocaleString('en-US', {
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

  // Transform data for better Excel formatting
  const transformedData = data.map(row => {
    const newRow = {};

    // Main fields
    newRow['Employee Name'] = row.user || '';
    newRow['Employee ID'] = row.hikvision_id || '';
    
    // Shift start time
    newRow['Shift Start Time'] = row.shift_start_time || '—';
    
    // First entry time
    newRow['First Entry Time'] = row.entry_time ? formatTimeExcel(row.entry_time) : 'N/A';
    
    // Delay
    newRow['Delay (minutes)'] = row.delay_minutes !== null && row.delay_minutes !== undefined 
      ? `${row.delay_minutes}` 
      : '—';
    
    // Last authentication
    newRow['Last Event Time'] = row.last_authentication ? formatTimeExcel(row.last_authentication) : 'N/A';
    
    // Shift duration
    if (row.shift_duration_hours !== null && row.shift_duration_hours !== undefined) {
      newRow['Shift Duration'] = formatHoursToTime(row.shift_duration_hours);
    } else {
      newRow['Shift Duration'] = '—';
    }
    
    // Hours in shift
    newRow['Hours in Shift'] = row.hours_in_shift !== null && row.hours_in_shift !== undefined
      ? formatHoursToTime(row.hours_in_shift)
      : '00:00';
    
    // Hours outside shift
    newRow['Hours Outside Shift'] = row.hours_outside_shift !== null && row.hours_outside_shift !== undefined
      ? formatHoursToTime(row.hours_outside_shift)
      : '00:00';
    
    // Total hours worked
    newRow['Total Hours Worked'] = row.hours_worked_total !== null && row.hours_worked_total !== undefined
      ? formatHoursToTime(row.hours_worked_total)
      : '00:00';
    
    // Entry/Exit type
    if (row.entry_exit_type) {
      newRow['Last Event Type'] = row.entry_exit_type === 'entry' ? 'Entry' : 'Exit';
    } else {
      newRow['Last Event Type'] = '—';
    }
    
    // Status
    const statusMap = {
      'Present': 'Present',
      'Absent': 'Absent',
      'Present (no exit)': 'Present (No Exit)'
    };
    newRow['Status'] = statusMap[row.status] || row.status || 'Unknown';

    return newRow;
  });

  // Create worksheet
  const worksheet = XLSX.utils.json_to_sheet(transformedData);
  
  // Configure column widths
  const colWidths = [
    { wch: 25 }, // Employee Name
    { wch: 15 }, // Employee ID
    { wch: 18 }, // Shift Start Time
    { wch: 22 }, // First Entry Time
    { wch: 15 }, // Delay
    { wch: 22 }, // Last Event Time
    { wch: 15 }, // Shift Duration
    { wch: 15 }, // Hours in Shift
    { wch: 18 }, // Hours Outside Shift
    { wch: 18 }, // Total Hours Worked
    { wch: 15 }, // Last Event Type
    { wch: 20 }  // Status
  ];
  worksheet['!cols'] = colWidths;
  
  // Create workbook
  const workbook = XLSX.utils.book_new();
  
  // Add sheet
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Attendance Report');
  
  // Save file
  XLSX.writeFile(workbook, `${filename}.xlsx`, {
    bookType: 'xlsx',
    type: 'array',
    cellStyles: true
  });
};
