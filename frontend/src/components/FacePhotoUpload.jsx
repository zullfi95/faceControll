import React, { useState } from 'react';
import showToast from '../utils/toast';

const FacePhotoUpload = ({ onPhotoSelect, currentPhoto }) => {
  const [preview, setPreview] = useState(currentPhoto || null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (file) => {
    if (!file) return;

    // Проверка типа файла
    if (!file.type.startsWith('image/')) {
      showToast.warning('Пожалуйста, выберите изображение');
      return;
    }

    // Проверка размера (макс 5MB)
    if (file.size > 5 * 1024 * 1024) {
      showToast.warning('Размер файла не должен превышать 5MB');
      return;
    }

    // Создание preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result);
    };
    reader.readAsDataURL(file);

    // Передаем файл родителю
    onPhotoSelect(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    handleFileChange(file);
  };

  const handleInputChange = (e) => {
    const file = e.target.files[0];
    handleFileChange(file);
  };

  return (
    <div className="w-full">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Фото для распознавания лица
      </label>
      
      <div
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
          isDragging
            ? 'border-[rgb(19,91,147)] bg-[rgb(235,245,252)]'
            : 'border-gray-300 hover:border-[rgb(19,91,147)]'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => document.getElementById('photo-upload').click()}
      >
        {preview ? (
          <div className="space-y-2">
            <img
              src={preview}
              alt="Preview"
              className="mx-auto h-48 w-48 object-cover rounded-lg"
            />
            <p className="text-sm text-gray-500">Нажмите или перетащите для замены</p>
          </div>
        ) : (
          <div className="space-y-2">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <div className="text-sm text-gray-600">
              <span className="font-medium text-[rgb(19,91,147)] hover:text-[rgb(30,120,180)]">
                Загрузите файл
              </span>{' '}
              или перетащите сюда
            </div>
            <p className="text-xs text-gray-500">PNG, JPG до 5MB</p>
          </div>
        )}
      </div>

      <input
        id="photo-upload"
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleInputChange}
      />

      <p className="mt-2 text-xs text-gray-500">
        Рекомендация: фото лица анфас, хорошее освещение, нейтральное выражение
      </p>
    </div>
  );
};

export default FacePhotoUpload;

