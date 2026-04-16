import Navbarhome from "../components/startPage/Navbarhome";
import Home from "../components/startPage/Home";
import About from "../components/startPage/About";
import Services from "../components/startPage/Services";
import FAQ from "../components/startPage/FAQ";
import Footer from "../components/startPage/Footer";

const StartPage = () => {
  return (
    <div>
      <Navbarhome />
      <main>
        <Home />
        <About />
        <Services />
        <FAQ />
      </main>
      <Footer />
    </div>
  );
};

export default StartPage;
