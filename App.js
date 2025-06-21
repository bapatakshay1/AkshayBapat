import React from 'react';
import ProfileCard from './ProfileCard.js';

function App() {
  const handleContactClick = () => {
    window.location.href = "mailto:Bapat.akshay1@gmail.com";
  };

  return (
    <div className="App">
      <ProfileCard
        name="Akshay Bapat"
        title="Software Engineer II & ML Engineer"
        handle="AkshayBapat"
        status="Available for opportunities"
        contactText="Contact Me"
        avatarUrl="me.jpg"
        showUserInfo={true}
        enableTilt={true}
        onContactClick={handleContactClick}
      />
    </div>
  );
}

export default App; 