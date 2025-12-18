/**
 * Hook personalizado para exportar Dashboard a PDF
 * Usa html2canvas + jsPDF para capturar TODO el contenido visual
 */
import { useState } from 'react';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

interface PDFExportOptions {
  filename?: string;
  quality?: number;
  scale?: number;
}

export const usePDFExport = () => {
  const [isExporting, setIsExporting] = useState(false);
  const [progress, setProgress] = useState(0);

  const exportToPDF = async (
    elementId: string,
    options: PDFExportOptions = {}
  ) => {
    const {
      filename = `reporte_${new Date().toISOString().split('T')[0]}.pdf`,
      quality = 0.95,
      scale = 2
    } = options;

    setIsExporting(true);
    setProgress(10);

    try {
      // 1. Obtener el elemento del dashboard
      const element = document.getElementById(elementId);
      if (!element) {
        throw new Error(`Elemento con id "${elementId}" no encontrado`);
      }

      setProgress(20);

      // 2. Ocultar elementos que no queremos en el PDF
      const elementsToHide = element.querySelectorAll('.no-print, button, .export-buttons');
      elementsToHide.forEach((el: any) => {
        el.style.display = 'none';
      });

      setProgress(30);

      // 3. Capturar el contenido con html2canvas
      const canvas = await html2canvas(element, {
        scale: scale,
        useCORS: true,
        logging: false,
        allowTaint: true,
        backgroundColor: '#ffffff',
        imageTimeout: 0,
        removeContainer: true,
        onclone: (clonedDoc) => {
          // Asegurar que las gráficas se rendericen correctamente
          const clonedElement = clonedDoc.getElementById(elementId);
          if (clonedElement) {
            clonedElement.style.width = '1200px';
            clonedElement.style.minHeight = 'auto';
          }
        }
      });

      setProgress(60);

      // 4. Crear el PDF
      const imgData = canvas.toDataURL('image/jpeg', quality);
      const imgWidth = 210; // A4 ancho en mm
      const pageHeight = 297; // A4 alto en mm
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;

      const pdf = new jsPDF('p', 'mm', 'a4');
      let position = 0;

      // Agregar primera página
      pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      setProgress(80);

      // Agregar páginas adicionales si es necesario
      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      setProgress(90);

      // 5. Descargar el PDF
      pdf.save(filename);

      setProgress(100);

      // 6. Restaurar elementos ocultos
      elementsToHide.forEach((el: any) => {
        el.style.display = '';
      });

      // Resetear después de un momento
      setTimeout(() => {
        setIsExporting(false);
        setProgress(0);
      }, 1000);

      return true;

    } catch (error) {
      console.error('Error exportando PDF:', error);
      setIsExporting(false);
      setProgress(0);
      throw error;
    }
  };

  return {
    exportToPDF,
    isExporting,
    progress
  };
};
