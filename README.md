<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/na-stewart/Quotech">
    <img src="https://github.com/na-stewart/Quotient/blob/master/resources/logo.png" alt="Logo" width="200" height="200">
  </a>
  <h3 align="center">Quotient</h3>
  <p align="center">
    Equity growth-at-a-reasonable-price (GARP) scoring model.
    <br />
    <br />
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

Comprehensive reporting designed to uncover potential long-term investment opportunities.

Features include customizable benchmarks, technical indicators, and dynamic screeners. 

Implement your own ideas and strategies with an extendable framework.

Powered with reliable market data through the Charles Schwab API.

<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple example steps.

### Prerequisites

Create an account and an application on the [Charles Schwab developer site](https://developer.schwab.com/login)
to receive an API key and app secret. You'll also want to take note of your 
callback URI as the login flow requires it. [You can find more detailed instructions here.](https://schwab-py.readthedocs.io/en/latest/getting-started.html)

### Installation

You can clone an instance or download from the releases.

1. Clone the repo or [download here](https://github.com/na-stewart/Quotient/releases).
   ```sh
   git clone https://github.com/na-stewart/Quotient
   ```
   
2. Install packages
   ```sh
   pip3 install -r requirements.txt
   ```
3. Make desired changes to the environment variables in the .env file, below is an example of its contents:

    ```dotenv
    SCHWAB_KEY=3I6aTEeD9wefwsdgfppO8gJUiq74Xu
    SCHWAB_SECRET=uuhsxjbixifZAysJ
    SCHWAB_CALLBACK=https://127.0.0.1:8000/schwab-cb
    ```
   
4. Run Quotient
   ```sh
   python3 main.py
   ```


<!-- USAGE EXAMPLES -->
## Usage

Quotient is snappy and interactive, with a console-based menu that lets you move as fast as the market.

### Start Program

<img src="https://github.com/na-stewart/Quotient/blob/master/screenshots/screenshot-1.png?raw=true" width="520">

### Create Watchlists

<img src="https://github.com/na-stewart/Quotient/blob/master/screenshots/screenshot-2.png?raw=true" width="520">

### Generate Reports

<img src="https://github.com/na-stewart/Quotient/blob/master/screenshots/screenshot-3.png?raw=true" width="520">

<img src="https://github.com/na-stewart/Quotient/blob/master/screenshots/report.png?raw=true" width="520">

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
