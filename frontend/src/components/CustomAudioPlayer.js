import React, { useState, useRef, useEffect } from 'react';

const PlayIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M8 5v14l11-7z" />
  </svg>
);

const PauseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
  </svg>
);

const CustomAudioPlayer = ({ src, avatar }) => {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState('0:00');
  const [duration, setDuration] = useState('0:00');
  const [playbackRate, setPlaybackRate] = useState(1);
  const [error, setError] = useState(false);

  const speeds = [1, 1.5, 2];

  // --- Funções de Controle ---

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
    } else {
      audio.play().catch(e => console.error("Erro ao reproduzir:", e));
    }
    setIsPlaying(!isPlaying);
  };

  const toggleSpeed = () => {
    const audio = audioRef.current;
    if (!audio) return;

    const nextIndex = (speeds.indexOf(playbackRate) + 1) % speeds.length;
    const nextSpeed = speeds[nextIndex];

    audio.playbackRate = nextSpeed;
    setPlaybackRate(nextSpeed);
  };

  const handleTimeUpdate = () => {
    const audio = audioRef.current;
    if (!audio) return;

    const current = audio.currentTime;
    const total = audio.duration || 0;

    const percent = (current / total) * 100;
    setProgress(percent);
    setCurrentTime(formatTime(current));
  };

  const handleLoadedMetadata = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.duration === Infinity) {
      setDuration("");
    } else {
      setDuration(formatTime(audio.duration));
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setProgress(0);
    setCurrentTime('0:00');
  };

  const handleError = () => {
    setError(true);
    console.warn("Áudio falhou ao carregar:", src);
  };

  const handleSeek = (e) => {
    const audio = audioRef.current;
    if (!audio || !audio.duration) return;

    const width = e.currentTarget.clientWidth;
    const clickX = e.nativeEvent.offsetX;
    const duration = audio.duration;

    audio.currentTime = (clickX / width) * duration;
  };

  const formatTime = (time) => {
    if (!time || isNaN(time)) return "0:00";
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
  };

  if (error) {
    return (
      <div style={{ color: '#f85149', fontSize: '0.8rem', padding: '10px', display: 'flex', alignItems: 'center', gap: '5px' }}>
        ⚠️ Áudio indisponível
      </div>
    );
  }

  return (
    <div className="custom-audio-player">
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        onError={handleError}
        preload="metadata"
      >
        <source src={src} type="audio/ogg" />
        <source src={src} type="audio/mpeg" />
        <source src={src} type="audio/mp4" />
        <source src={src} />
      </audio>

      {/* Avatar com ícone de mic (Estilo WhatsApp) */}
      <div className="audio-avatar-container">
        <img src={avatar || "https://cdn-icons-png.flaticon.com/512/149/149071.png"} alt="Avatar" className="audio-avatar" />
        <div className="audio-mic-badge">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="white"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" /><path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" /></svg>
        </div>
      </div>

      <button className="audio-control-btn" onClick={togglePlay}>
        {isPlaying ? <PauseIcon /> : <PlayIcon />}
      </button>

      <div className="audio-track-container">
        <div className="audio-progress-bar" onClick={handleSeek}>
          <div
            className="audio-progress-fill"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        <div className="audio-timers">
          <span>{currentTime}</span>
          <span>{duration}</span>
        </div>
      </div>

      {/* Botão de velocidade (Opcional, pode ficar escondido ou no final) */}
      <button className="speed-btn" onClick={toggleSpeed}>
        {playbackRate}x
      </button>
    </div>
  );
};

export default CustomAudioPlayer;