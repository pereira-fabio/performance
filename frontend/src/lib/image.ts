/**
 * Prepare a picture for upload.
 *
 * Scaled and cropped in the browser rather than on the server: a phone photo
 * is several megabytes and is about to be drawn at 56 pixels, so sending the
 * original would waste the upload, the disk and the bandwidth of every later
 * page load. It also means the server needs no image library, which keeps the
 * container buildable anywhere.
 *
 * Cropped to a square from the centre, because that is how it will be shown --
 * scaling a portrait into a circle without cropping squashes the face.
 */
export const SIZE = 256;

export const squareThumbnail = (file: File, size = SIZE): Promise<Blob> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('That file could not be read.'));
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => reject(new Error('That file is not an image.'));
      image.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = size;
        const ctx = canvas.getContext('2d');
        if (!ctx) return reject(new Error('Your browser could not process the image.'));

        const side = Math.min(image.width, image.height);
        ctx.drawImage(
          image,
          (image.width - side) / 2, (image.height - side) / 2, side, side,
          0, 0, size, size
        );
        canvas.toBlob(
          (blob) => (blob ? resolve(blob) : reject(new Error('Could not prepare the image.'))),
          'image/jpeg',
          0.85
        );
      };
      image.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
