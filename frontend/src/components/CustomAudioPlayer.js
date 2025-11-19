import React, { useState, useRef, useEffect } from 'react';

const PlayIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M8 5v14l11-7z"/>
  </svg>
);

const PauseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
  </svg>
);

const CustomAudioPlayer = ({ src }) => {
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

  // 💡 A FUNÇÃO QUE FALTAVA
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
    if(!audio || !audio.duration) return;

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
      <div style={{color: '#f85149', fontSize: '0.8rem', padding: '10px', display: 'flex', alignItems: 'center', gap: '5px'}}>
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
        onEnded={handleEnded} // Agora a função existe!
        onError={handleError}
        preload="metadata"
      >
        <source src={src} type="audio/ogg" />
        <source src={src} type="audio/mpeg" />
        <source src={src} type="audio/mp4" />
        <source src={src} />
      </audio>

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

      <button className="speed-btn" onClick={toggleSpeed}>
        {playbackRate}x
      </button>
    </div>
  );
};

export default CustomAudioPlayer;